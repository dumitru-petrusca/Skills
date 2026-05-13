package main

import (
	"context"
	"fmt"

	"gcp_cost_optimizer/tools"

	"golang.org/x/oauth2/google"
	"google.golang.org/adk/agent"
	"google.golang.org/adk/agent/llmagent"
	"google.golang.org/adk/model"
	"google.golang.org/adk/tool"
)

func detectProject() string {
	ctx := context.Background()
	credentials, err := google.FindDefaultCredentials(ctx)
	if err == nil && credentials.ProjectID != "" {
		return credentials.ProjectID
	}
	return ""
}

func buildInstruction() string {
	project := detectProject()
	projectLine := ""
	if project != "" {
		projectLine = fmt.Sprintf("Your default GCP project is **%s**. Use this as the project_id for tool calls unless the user specifies a different project.\n\n", project)
	}

	return fmt.Sprintf(`You are a GCP cost optimization expert with access to real-time data.

%sYour job:
- Discover all resources in a GCP project
- Identify candidates for cost reduction: resources to downsize, idle resources to delete, unnecessary services to disable
- Query billing data to quantify actual spend
- Order everything by estimated cost impact — biggest savings opportunities first

Tools available:
- list_resources: discover all GCP resources via Cloud Asset Inventory. This is your primary discovery tool — it shows everything deployed in the project.
- list_running_vms: list running Compute Engine instances with machine types. Use this to identify oversized or idle VMs.
- list_gke_clusters: list GKE clusters with node counts and machine types.
- list_cloud_run_services: list Cloud Run services in a region.
- list_agent_engines: list deployed Vertex AI Agent Engine (Reasoning Engine) instances.
- query_billing: query the BigQuery billing export for cost by service and SKU. The billing_table parameter is optional — if omitted, the tool auto-discovers the export table. Billing export may not be configured in every project. If the tool returns an error or no data, skip billing and work with inventory data only.

Workflow:
1. Start by listing all resources in the project.
2. Identify resource types that cost money (VMs, GKE, storage, Reasoning Engines, Cloud Run, Discovery Engine, etc.)
3. Drill into specific resource types with the specialized tools.
4. If the user provides a billing table, query it to get actual spend data.
5. Present findings ordered by cost impact (highest first).

Output format:
- Lead with a resource inventory summary (type, count)
- Then list resources with cost details, each with:
  - What the resource is (specific name, not just type)
  - Estimated cost category (high/medium/low based on resource type and size)
  - Current spend if billing data is available
- Group by priority: High (VMs, GKE clusters, Reasoning Engines, databases), Medium (storage, Cloud Run, Docker images), Low (service accounts, tags, roles)

Rules:
- Always call tools to get real data before answering. Never guess.
- If a tool returns no data, say so clearly.
- Be specific — name the actual resources, not just categories.`, projectLine)
}

func CreateAgent(m model.LLM) (agent.Agent, error) {
	listResourcesTool, err := tools.NewListResourcesTool()
	if err != nil {
		return nil, fmt.Errorf("creating list_resources tool: %w", err)
	}

	listRunningVMsTool, err := tools.NewListRunningVMsTool()
	if err != nil {
		return nil, fmt.Errorf("creating list_running_vms tool: %w", err)
	}

	listGKEClustersTool, err := tools.NewListGKEClustersTool()
	if err != nil {
		return nil, fmt.Errorf("creating list_gke_clusters tool: %w", err)
	}

	listCloudRunServicesTool, err := tools.NewListCloudRunServicesTool()
	if err != nil {
		return nil, fmt.Errorf("creating list_cloud_run_services tool: %w", err)
	}

	listAgentEnginesTool, err := tools.NewListAgentEnginesTool()
	if err != nil {
		return nil, fmt.Errorf("creating list_agent_engines tool: %w", err)
	}

	queryBillingTool, err := tools.NewQueryBillingTool()
	if err != nil {
		return nil, fmt.Errorf("creating query_billing tool: %w", err)
	}

	return llmagent.New(llmagent.Config{
		Name:        "gcp_cost_optimizer",
		Model:       m,
		Description: "Analyzes GCP resources and surfaces cost optimization recommendations.",
		Instruction: buildInstruction(),
		Tools: []tool.Tool{
			listResourcesTool,
			listRunningVMsTool,
			listGKEClustersTool,
			listCloudRunServicesTool,
			listAgentEnginesTool,
			queryBillingTool,
		},
	})
}
