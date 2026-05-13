package tools

import (
	"context"
	"fmt"
	"math"
	"sort"
	"strings"

	"cloud.google.com/go/bigquery"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
	"google.golang.org/api/iterator"
)

type QueryBillingArgs struct {
	ProjectID    string `json:"project_id" description:"The GCP project ID to query billing for."`
	BillingTable string `json:"billing_table,omitempty" description:"Fully qualified BigQuery table name, e.g. 'project.billing_export.gcp_billing_export_v1_XXXXXX'. If empty, attempts to auto-discover the billing export table in the 'billing_export' dataset."`
	Days         int    `json:"days,omitempty" description:"Number of days to look back (default 30)."`
}

type ServiceCost struct {
	Service string  `json:"service"`
	Cost    float64 `json:"cost"`
}

type TopSKU struct {
	Service string  `json:"service"`
	SKU     string  `json:"sku"`
	Cost    float64 `json:"cost"`
}

type QueryBillingResult struct {
	Error     string        `json:"error,omitempty"`
	TotalCost float64       `json:"total_cost"`
	ByService []ServiceCost `json:"by_service"`
	TopSKUs   []TopSKU      `json:"top_skus"`
	Currency  string        `json:"currency"`
}

func NewQueryBillingTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name:        "query_billing",
		Description: "Query the BigQuery billing export for cost by service and SKU. The billing_table parameter is optional — if omitted, the tool auto-discovers the export table. Billing export may not be configured in every project. If the tool returns an error or no data, skip billing and work with inventory data only.",
	}, QueryBilling)
}

type billingRow struct {
	Service  string  `bigquery:"service"`
	SKU      string  `bigquery:"sku"`
	NetCost  float64 `bigquery:"net_cost"`
	Currency string  `bigquery:"currency"`
}

func QueryBilling(ctx tool.Context, args QueryBillingArgs) (QueryBillingResult, error) {
	if args.Days <= 0 {
		args.Days = 30
	}

	client, err := bigquery.NewClient(ctx, args.ProjectID)
	if err != nil {
		return QueryBillingResult{}, fmt.Errorf("creating bigquery client: %w", err)
	}
	defer client.Close()

	billingTable := args.BillingTable
	if billingTable == "" {
		billingTable = discoverBillingTable(ctx, client, args.ProjectID)
		if billingTable == "" {
			return QueryBillingResult{
				Error:     "No billing export table found. Billing export may not be configured. See: https://cloud.google.com/billing/docs/how-to/export-data-bigquery",
				TotalCost: 0,
				ByService: []ServiceCost{},
				TopSKUs:   []TopSKU{},
				Currency:  "USD",
			}, nil
		}
	}

	queryStr := fmt.Sprintf(`
    SELECT
        service.description AS service,
        sku.description AS sku,
        SUM(cost) + SUM(IFNULL(
            (SELECT SUM(c.amount) FROM UNNEST(credits) c), 0
        )) AS net_cost,
        currency
    FROM `+"`"+`%s`+"`"+`
    WHERE usage_start_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL %d DAY)
      AND project.id = @project_id
    GROUP BY service, sku, currency
    ORDER BY net_cost DESC
    `, billingTable, args.Days)

	q := client.Query(queryStr)
	q.Parameters = []bigquery.QueryParameter{
		{Name: "project_id", Value: args.ProjectID},
	}

	it, err := q.Read(ctx)
	if err != nil {
		return QueryBillingResult{}, fmt.Errorf("executing billing query: %w", err)
	}

	var rows []billingRow
	for {
		var row billingRow
		err := it.Next(&row)
		if err == iterator.Done {
			break
		}
		if err != nil {
			return QueryBillingResult{}, fmt.Errorf("iterating billing query results: %w", err)
		}
		rows = append(rows, row)
	}

	if len(rows) == 0 {
		return QueryBillingResult{
			TotalCost: 0,
			ByService: []ServiceCost{},
			TopSKUs:   []TopSKU{},
			Currency:  "USD",
		}, nil
	}

	currency := rows[0].Currency
	if currency == "" {
		currency = "USD"
	}

	byServiceMap := make(map[string]float64)
	var topSKUs []TopSKU

	for i, r := range rows {
		byServiceMap[r.Service] += r.NetCost
		if i < 20 {
			topSKUs = append(topSKUs, TopSKU{
				Service: r.Service,
				SKU:     r.SKU,
				Cost:    round2(r.NetCost),
			})
		}
	}

	var byService []ServiceCost
	var totalCost float64
	for s, c := range byServiceMap {
		byService = append(byService, ServiceCost{
			Service: s,
			Cost:    round2(c),
		})
		totalCost += c
	}

	sort.Slice(byService, func(i, j int) bool {
		return byService[i].Cost > byService[j].Cost
	})

	return QueryBillingResult{
		TotalCost: round2(totalCost),
		ByService: byService,
		TopSKUs:   topSKUs,
		Currency:  currency,
	}, nil
}

func discoverBillingTable(ctx context.Context, client *bigquery.Client, projectID string) string {
	dataset := client.DatasetInProject(projectID, "billing_export")
	it := dataset.Tables(ctx)
	for {
		t, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return ""
		}
		if strings.HasPrefix(t.TableID, "gcp_billing_export") {
			return fmt.Sprintf("%s.billing_export.%s", projectID, t.TableID)
		}
	}
	return ""
}

func round2(val float64) float64 {
	return math.Round(val*100) / 100
}
