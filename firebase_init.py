import json
from google.cloud import secretmanager
from firebase_admin import credentials, initialize_app
from config import GCP_PROJECT_ID, SERVICE_ACCOUNT_SECRET_ID, SERVICE_ACCOUNT_SECRET_NAME

def get_service_account_info(secret_id, secret_name):
    client = secretmanager.SecretManagerServiceClient()
    print(secret_id)
    print(secret_name)
    name = f"projects/{secret_id}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(name=name)
    secret_string = response.payload.data.decode("UTF-8")
    return json.loads(secret_string)

def init_firebase():
    secret_id = SERVICE_ACCOUNT_SECRET_ID
    secret_name = SERVICE_ACCOUNT_SECRET_NAME
    service_account_info = get_service_account_info(secret_id, secret_name)
    cred = credentials.Certificate(service_account_info)
    initialize_app(cred)

# Initialize Firebase when this module is imported
init_firebase()
