package main

var methodToPermissions = map[string][]string{
	// Compute Engine
	"cloud.google.com/go/compute/apiv1.InstancesClient.AggregatedList": {"compute.instances.list"},
	"cloud.google.com/go/compute/apiv1.InstancesClient.List":           {"compute.instances.list"},

	// GKE (Kubernetes Engine)
	"cloud.google.com/go/container/apiv1.ClusterManagerClient.ListClusters": {"container.clusters.list"},
	"cloud.google.com/go/container/apiv1.ClusterManagerClient.GetCluster":   {"container.clusters.get"},

	// Cloud Asset Inventory
	"cloud.google.com/go/asset/apiv1.Client.ListAssets": {"cloudasset.assets.searchAllResources"},

	// BigQuery
	"cloud.google.com/go/bigquery.Client.Query":            {"bigquery.jobs.create"},
	"cloud.google.com/go/bigquery.Dataset.Tables":          {"bigquery.tables.list"},
	"cloud.google.com/go/bigquery.Client.DatasetInProject": {"bigquery.datasets.get"},
	"cloud.google.com/go/bigquery.Client.Dataset":          {"bigquery.datasets.get"},

	// Cloud Run
	"cloud.google.com/go/run/apiv2.ServicesClient.ListServices": {"run.services.list"},
	"cloud.google.com/go/run/apiv2.ServicesClient.GetService":  {"run.services.get"},
}

func Gapic2Permission(gapicMethod string) []string {
	return methodToPermissions[gapicMethod]
}
