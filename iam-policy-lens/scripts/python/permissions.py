from typing import List, Optional

# Static mapping of resolved GAPIC methods to required IAM permissions
_METHOD_TO_PERMISSIONS = {
    # Compute Engine
    "google.cloud.compute_v1.InstancesClient.aggregated_list": ["compute.instances.list"],
    "google.cloud.compute_v1.InstancesClient.list": ["compute.instances.list"],
    
    # GKE (Kubernetes Engine)
    "google.cloud.container_v1.ClusterManagerClient.list_clusters": ["container.clusters.list"],
    "google.cloud.container_v1.ClusterManagerClient.get_cluster": ["container.clusters.get"],
    
    # Cloud Asset Inventory
    "google.cloud.asset_v1.AssetServiceClient.list_assets": ["cloudasset.assets.searchAllResources"],
    
    # BigQuery
    "google.cloud.bigquery.Client.query": ["bigquery.jobs.create"],
    "google.cloud.bigquery.Client.list_tables": ["bigquery.tables.list"],
    "google.cloud.bigquery.Client.get_dataset": ["bigquery.datasets.get"],
    "google.cloud.bigquery.Client.create_dataset": ["bigquery.datasets.create"],
    "google.cloud.bigquery.Client.load_table_from_file": [
        "bigquery.tables.create",
        "bigquery.tables.updateData"
    ],
    "google.cloud.bigquery.dataset.Dataset": ["bigquery.datasets.get"],
    "google.cloud.bigquery.dataset.DatasetReference": ["bigquery.datasets.get"],
    "google.cloud.bigquery.table.TableReference": ["bigquery.tables.get"],
    
    # Cloud Storage
    "google.cloud.storage.Client.lookup_bucket": ["storage.buckets.get"],
    "google.cloud.storage.Client.create_bucket": ["storage.buckets.create"],
    "google.cloud.storage.bucket.Bucket.patch": ["storage.buckets.update"],
    
    # Vertex AI / reasoning engine
    "vertexai.agent_engines.create": [
        "aiplatform.reasoningEngines.create",
        "storage.buckets.create",
        "storage.buckets.get"
    ],
    "vertexai.agent_engines.get": ["aiplatform.reasoningEngines.get"],
    "vertexai.agent_engines.delete": ["aiplatform.reasoningEngines.delete"],
}

def gapic2permission(gapic_method: str) -> Optional[List[str]]:
    """Maps a fully qualified GAPIC method call string to its required IAM permissions list."""
    return _METHOD_TO_PERMISSIONS.get(gapic_method)
