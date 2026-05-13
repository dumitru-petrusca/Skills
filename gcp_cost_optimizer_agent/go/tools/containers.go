package tools

import (
	"fmt"

	container "cloud.google.com/go/container/apiv1"
	"cloud.google.com/go/container/apiv1/containerpb"
	run "cloud.google.com/go/run/apiv2"
	"cloud.google.com/go/run/apiv2/runpb"
	"google.golang.org/adk/tool"
	"google.golang.org/adk/tool/functiontool"
	"google.golang.org/api/iterator"
)

// GKE structures

type ListGKEClustersArgs struct {
	ProjectID string `json:"project_id" description:"The GCP project ID."`
}

type GKEClusterInfo struct {
	Name          string `json:"name"`
	Location      string `json:"location"`
	Status        string `json:"status"`
	NodeCount     int    `json:"node_count"`
	MachineType   string `json:"machine_type"`
	MasterVersion string `json:"master_version"`
}

type ListGKEClustersResult struct {
	Total    int              `json:"total"`
	Clusters []GKEClusterInfo `json:"clusters"`
}

func NewListGKEClustersTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name:        "list_gke_clusters",
		Description: "List GKE clusters with node counts and machine types in a project.",
	}, ListGKEClusters)
}

func ListGKEClusters(ctx tool.Context, args ListGKEClustersArgs) (ListGKEClustersResult, error) {
	client, err := container.NewClusterManagerClient(ctx)
	if err != nil {
		return ListGKEClustersResult{}, fmt.Errorf("creating cluster manager client: %w", err)
	}
	defer client.Close()

	// Parent resource in the format 'projects/PROJECT_ID/locations/LOCATION'
	// Using '-' as location to list clusters in all locations.
	parent := fmt.Sprintf("projects/%s/locations/-", args.ProjectID)
	req := &containerpb.ListClustersRequest{
		Parent: parent,
	}

	resp, err := client.ListClusters(ctx, req)
	if err != nil {
		return ListGKEClustersResult{}, fmt.Errorf("listing GKE clusters: %w", err)
	}

	var clusters []GKEClusterInfo
	for _, c := range resp.Clusters {
		clusters = append(clusters, formatCluster(c))
	}

	return ListGKEClustersResult{
		Total:    len(clusters),
		Clusters: clusters,
	}, nil
}

func formatCluster(c *containerpb.Cluster) GKEClusterInfo {
	nodeCount := 0
	machineType := ""

	for _, pool := range c.NodePools {
		nodeCount += int(pool.InitialNodeCount)
		if machineType == "" && pool.Config != nil {
			machineType = pool.Config.MachineType
		}
	}

	return GKEClusterInfo{
		Name:          c.Name,
		Location:      c.Location,
		Status:        c.Status.String(),
		NodeCount:     nodeCount,
		MachineType:   machineType,
		MasterVersion: c.CurrentMasterVersion,
	}
}

// Cloud Run structures

type ListCloudRunServicesArgs struct {
	ProjectID string `json:"project_id" description:"The GCP project ID."`
	Region    string `json:"region,omitempty" description:"Region to query (default 'us-central1')."`
}

type CloudRunServiceInfo struct {
	Name         string `json:"name"`
	Region       string `json:"region"`
	URI          string `json:"uri"`
	LastModifier string `json:"last_modifier"`
	UpdateTime   string `json:"update_time"`
}

type ListCloudRunServicesResult struct {
	Total    int                   `json:"total"`
	Services []CloudRunServiceInfo `json:"services"`
}

func NewListCloudRunServicesTool() (tool.Tool, error) {
	return functiontool.New(functiontool.Config{
		Name:        "list_cloud_run_services",
		Description: "List Cloud Run services in a project and region.",
	}, ListCloudRunServices)
}

func ListCloudRunServices(ctx tool.Context, args ListCloudRunServicesArgs) (ListCloudRunServicesResult, error) {
	if args.Region == "" {
		args.Region = "us-central1"
	}

	client, err := run.NewServicesClient(ctx)
	if err != nil {
		return ListCloudRunServicesResult{}, fmt.Errorf("creating Cloud Run services client: %w", err)
	}
	defer client.Close()

	parent := fmt.Sprintf("projects/%s/locations/%s", args.ProjectID, args.Region)
	req := &runpb.ListServicesRequest{
		Parent: parent,
	}

	var services []CloudRunServiceInfo
	it := client.ListServices(ctx, req)
	for {
		svc, err := it.Next()
		if err == iterator.Done {
			break
		}
		if err != nil {
			return ListCloudRunServicesResult{}, fmt.Errorf("iterating Cloud Run services: %w", err)
		}
		services = append(services, formatRunService(svc, args.Region))
	}

	return ListCloudRunServicesResult{
		Total:    len(services),
		Services: services,
	}, nil
}

func formatRunService(svc *runpb.Service, region string) CloudRunServiceInfo {
	name := svc.Name
	// Extract last component of name (format is projects/PROJECT_ID/locations/REGION/services/SERVICE_NAME)
	if idx := len(name) - 1; idx >= 0 {
		for i := len(name) - 1; i >= 0; i-- {
			if name[i] == '/' {
				name = name[i+1:]
				break
			}
		}
	}

	updateTime := ""
	if svc.UpdateTime != nil {
		updateTime = svc.UpdateTime.AsTime().Format("2006-01-02T15:04:05Z07:00")
	}

	return CloudRunServiceInfo{
		Name:         name,
		Region:       region,
		URI:          svc.Uri,
		LastModifier: svc.LastModifier,
		UpdateTime:   updateTime,
	}
}
