import json
from google.cloud import secretmanager
from firebase_admin import credentials, initialize_app
from config.config import SERVICE_ACCOUNT_SECRET_ID, SERVICE_ACCOUNT_SECRET_NAME
from config.logger_config import setup_logger

logger = setup_logger(__name__)

def get_service_account_info(secret_id, secret_name):
    client = secretmanager.SecretManagerServiceClient()
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
    logger.info("Firebase initialized successfully.")

# Initialize Firebase when this module is imported
init_firebase()
