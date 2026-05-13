from google.cloud import compute_v1
from google.cloud import container_v1
from google.oauth2 import service_account


# Global scope
client = compute_v1.InstancesClient()

def scan_compute():
    # Uses global client
    # Should resolve to compute_v1.InstancesClient.aggregated_list
    for zone, instances in client.aggregated_list(project="my-project"):
        pass

def scan_both():
    # Shadows global client
    credentials = service_account.Credentials.from_service_account_file("/path/to/my-key.json")
    client = container_v1.ClusterManagerClient(credentials=credentials)
    
    # Should resolve to container_v1.ClusterManagerClient.list_clusters
    response = client.list_clusters(parent="projects/my-project/locations/-")
    
    def inner_scan():
        # Shadows enclosing client
        client = compute_v1.InstancesClient()
        # Should resolve to compute_v1.InstancesClient.aggregated_list
        for zone, instances in client.aggregated_list(project="my-project"):
            pass
            
    inner_scan()
