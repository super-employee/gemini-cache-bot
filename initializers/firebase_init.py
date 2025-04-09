import json
import sys
from google.cloud import secretmanager
from google.api_core import exceptions as google_exceptions
import firebase_admin
from firebase_admin import credentials
from config.config import (
    GCP_PROJECT_ID, SERVICE_ACCOUNT_SECRET_ID,
    SERVICE_ACCOUNT_SECRET_NAME, SERVICE_ACCOUNT_SECRET_VERSION, LOG_LEVEL
)
from config.logger_config import setup_logger

# Initialize logger early to catch potential init errors
logger = setup_logger(__name__, level=LOG_LEVEL)

def get_service_account_info(project_id, secret_id, secret_name, version="latest") -> dict:
    """
    Fetches the service account JSON key from Google Secret Manager.

    Args:
        project_id: Google Cloud Project ID.
        secret_id: The ID of the secret.
        secret_name: The name of the secret.
        version: The secret version (default: "latest").

    Returns:
        A dictionary representing the service account JSON key.

    Raises:
        ValueError: If secret payload is invalid JSON.
        google_exceptions.GoogleAPIError: If fetching the secret fails.
        Exception: For other unexpected errors.
    """
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
        logger.info(f"Attempting to access secret: {name}")
        response = client.access_secret_version(name=name)
        secret_string = response.payload.data.decode("UTF-8")
        logger.info("Secret payload retrieved successfully.")
        return json.loads(secret_string)
    except google_exceptions.NotFound:
        logger.critical(f"Secret or version not found: {name}")
        raise
    except google_exceptions.PermissionDenied:
        logger.critical(f"Permission denied accessing secret: {name}. Check IAM permissions for Secret Manager Secret Accessor role.")
        raise
    except json.JSONDecodeError as e:
        logger.critical(f"Failed to decode secret payload into JSON: {e}")
        raise ValueError("Invalid JSON format in secret payload") from e
    except Exception as e:
        logger.critical(f"Failed to retrieve service account info from Secret Manager: {e}", exc_info=True)
        raise

def init_firebase():
    """Initializes the Firebase Admin SDK using credentials from Secret Manager."""
    # Check if Firebase app is already initialized to prevent errors on re-import
    if not firebase_admin._apps:
        try:
            logger.info("Initializing Firebase Admin SDK...")
            service_account_info = get_service_account_info(
                GCP_PROJECT_ID,
                SERVICE_ACCOUNT_SECRET_ID,
                SERVICE_ACCOUNT_SECRET_NAME,
                SERVICE_ACCOUNT_SECRET_VERSION
            )
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully.")
        except (ValueError, google_exceptions.GoogleAPIError, Exception) as e:
            # Log critical error and exit? Or let the caller handle the failure.
            # For a critical dependency like Firebase, exiting might be appropriate.
            logger.critical(f"CRITICAL: Firebase initialization failed: {e}", exc_info=True)
            # Optionally, raise an exception to halt application startup
            raise SystemExit("Failed to initialize Firebase Admin SDK.") from e
    else:
        logger.debug("Firebase Admin SDK already initialized.")

# --- Initialize Firebase when this module is imported ---
# This ensures Firebase is ready before other modules try to use firestore.client()
try:
    init_firebase()
    # Verify Firestore client access immediately after init
    from firebase_admin import firestore
    db_client = firestore.client()
    logger.info("Firestore client accessed successfully post-initialization.")
except Exception as e:
     # If init_firebase or firestore.client() fails, the app likely can't run.
     # The error is logged within init_firebase or here.
     # Consider exiting here if not handled by init_firebase's SystemExit.
     logger.critical(f"Failed to verify Firestore client after Firebase init: {e}")
     sys.exit(1) # Exit if critical initialization fails