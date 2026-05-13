package tools

import (
	"fmt"
	"sort"

	asset "cloud.google.com/go/asset/apiv1"
	"cloud.google.com/go/asset/apiv1/assetpb"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
	"google.golang.org/api/iterator"
)

type ListResourcesArgs struct {
	ProjectID  string   `json:"project_id" description:"The GCP project ID (e.g. 'my-project')."`
	AssetTypes []string `json:"asset_types,omitempty" description:"Optional list of asset types to filter by, e.g. ['compute.googleapis.com/Instance', 'storage.googleapis.com/Bucket']. If omitted, returns all resource types."`
}

type AssetSummaryItem struct {
	AssetType string `json:"asset_type"`
	Count     int    `json:"count"`
}

type ListResourcesResult struct {
	Total   int                 `json:"total"`
	ByType  map[string][]string `json:"by_type"`
	Summary []AssetSummaryItem  `json:"summary"`
}

func NewListResourcesTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name:        "list_resources",
		Description: "List all GCP resources in a project via Cloud Asset Inventory, grouped by type. This is your primary discovery tool — it shows everything deployed in the project.",
	}, ListResources)
}

func ListResources(ctx tool.Context, args ListResourcesArgs) (ListResourcesResult, error) {
	c, err := asset.NewClient(ctx)
	if err != nil {
		return ListResourcesResult{}, fmt.Errorf("creating asset client: %w", err)
	}
	defer c.Close()

	req := &assetpb.ListAssetsRequest{
		Parent:      fmt.Sprintf("projects/%s", args.ProjectID),
		AssetTypes:  args.AssetTypes,
		ContentType: assetpb.ContentType_RESOURCE,
		PageSize:    1000,
	}

	byType := make(map[string][]string)
	it := c.ListAssets(ctx, req)
	for {
		resp, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return ListResourcesResult{}, fmt.Errorf("iterating assets: %w", err)
		}
		byType[resp.AssetType] = append(byType[resp.AssetType], resp.Name)
	}

	var summary []AssetSummaryItem
	total := 0
	for t, names := range byType {
		summary = append(summary, AssetSummaryItem{
			AssetType: t,
			Count:     len(names),
		})
		total += len(names)
	}

	sort.Slice(summary, func(i, j int) bool {
		return summary[i].Count > summary[j].Count
	})

	return ListResourcesResult{
		Total:   total,
		ByType:  byType,
		Summary: summary,
	}, nil
}
