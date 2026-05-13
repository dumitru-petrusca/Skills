import google.auth
from google.cloud import container_v1
from google.oauth2 import service_account

def exercise_dwd():
    # 1. Domain-Wide Delegation (DWD) pattern -> maps to DWD / IMPERSONATED
    creds = service_account.Credentials.from_service_account_file(
        'key.json',
        scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    dwd_creds = creds.with_subject('user@my-domain.com')
    client = container_v1.ClusterManagerClient(credentials=dwd_creds)
    return client

def exercise_explicit_adc():
    # 2. Explicit Application Default Credentials (ADC) -> maps to SA_DEFAULT / APP
    creds, project = google.auth.default()
    client = container_v1.ClusterManagerClient(credentials=creds)
    return client
