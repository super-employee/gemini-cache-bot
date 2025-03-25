import json
import os
from google.cloud import secretmanager
from firebase_admin import credentials, initialize_app
from config import GCP_PROJECT_ID, SERVICE_ACCOUNT_SECRET_ID

def get_service_account_info(project_id, secret_id):
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(name=name)
    secret_string = response.payload.data.decode("UTF-8")
    return json.loads(secret_string)

def init_firebase():
    project_id = os.getenv(GCP_PROJECT_ID)
    secret_id = os.getenv(SERVICE_ACCOUNT_SECRET_ID)
    service_account_info = get_service_account_info(project_id, secret_id)
    cred = credentials.Certificate(service_account_info)
    initialize_app(cred)

# Initialize Firebase when this module is imported
init_firebase()
