from google.cloud import container_v1
from google.oauth2 import credentials
from google.oauth2 import impersonated_credentials
from google_auth_oauthlib.flow import InstalledAppFlow

def exercise_oauth_flow():
    # 1. OAuth Flow pattern
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secrets.json',
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    creds = flow.run_local_server(port=0)
    
    client = container_v1.ClusterManagerClient(credentials=creds)
    return client

def exercise_oauth_user():
    # 2. OAuth User credentials loaded from authorized user file
    creds = credentials.Credentials.from_authorized_user_file('authorized_user.json')
    client = container_v1.ClusterManagerClient(credentials=creds)
    return client

def exercise_impersonation(source_creds):
    # 3. Service account impersonation credentials
    creds = impersonated_credentials.Credentials(
        source_credentials=source_creds,
        target_principal="target-service-account@project.iam.gserviceaccount.com",
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    client = container_v1.ClusterManagerClient(credentials=creds)
    return client
