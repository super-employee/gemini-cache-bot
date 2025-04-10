import os
import logging

# For Local Development
from dotenv import load_dotenv # Make sure to pip install 'dotenv' if using this
load_dotenv()  # Load environment variables from .env file for local development

# --- Environment Variable Helper ---
def get_env_variable(var_name, default=None, required=False):
    """Gets an environment variable, logs, and raises error if required and missing."""
    value = os.getenv(var_name, default)
    if required and value is None:
        logging.critical(f"CRITICAL: Required environment variable '{var_name}' is not set.")
        raise ValueError(f"Missing required environment variable: {var_name}")
    if value is None:
         logging.warning(f"Optional environment variable '{var_name}' not set, using default: {default}")
    else:
        # Avoid logging sensitive values like secret names directly
        log_value = value if not any(s in var_name.lower() for s in ['secret', 'key', 'password']) else '******'
        logging.debug(f"Environment variable '{var_name}': {log_value}")
    return value

# --- Logging Configuration ---
LOG_LEVEL_STR = get_env_variable("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

# --- Gunicorn Configuration ---
GUNICORN_WORKERS = int(get_env_variable("GUNICORN_WORKERS", "2")) # Default to 2 workers

# --- Google Cloud Settings ---
GCP_PROJECT_ID = get_env_variable("GCP_PROJECT_ID", required=True)

# --- Secret Manager Settings ---
SERVICE_ACCOUNT_SECRET_ID = get_env_variable("SERVICE_ACCOUNT_SECRET_ID", required=True)
SERVICE_ACCOUNT_SECRET_NAME = get_env_variable("SERVICE_ACCOUNT_SECRET_NAME", required=True)
# Assuming latest version - adjust if specific version needed
SERVICE_ACCOUNT_SECRET_VERSION = get_env_variable("SERVICE_ACCOUNT_SECRET_VERSION", "latest")

# --- Firestore Document Paths and Fields ---
# It's crucial these paths are correct for your Firestore structure
CACHE_CONFIG_DOC_PATH = get_env_variable("CACHE_CONFIG_DOC_PATH", required=True)
SYSTEM_PROMPT_DOC_PATH = get_env_variable("SYSTEM_PROMPT_DOC_PATH", required=True)
INVENTORY_DATA_DOC_PATH = get_env_variable("INVENTORY_DATA_DOC_PATH", required=True)

ACTIVE_CACHE_FIELD = get_env_variable("ACTIVE_CACHE_FIELD", "activeCache")
UPDATED_AT_FIELD = get_env_variable("UPDATED_AT_FIELD", "updatedAt")
EXPIRES_AT_FIELD = get_env_variable("EXPIRES_AT_FIELD", "expiresAt")
SYSTEM_PROMPT_FIELD = get_env_variable("SYSTEM_PROMPT_FIELD", "prompt")
INVENTORY_DATA_FIELD = get_env_variable("INVENTORY_DATA_FIELD", "inventory")

# --- Gemini Model and Cache Settings ---
GOOGLE_API_KEY = get_env_variable("GOOGLE_API_KEY", required=True)
GEMINI_MODEL_NAME = get_env_variable("GEMINI_MODEL_NAME", "models/gemini-1.5-flash-002")
# Cache Time-To-Live in seconds (e.g., 15 minutes)
CACHE_TTL_SECONDS = int(get_env_variable("CACHE_TTL_SECONDS", 900))
# Threshold before expiry to trigger extension (seconds)
CACHE_EXTENSION_THRESHOLD = int(get_env_variable("CACHE_EXTENSION_THRESHOLD", 300))
# Duration to extend the cache by (seconds)
CACHE_EXTENSION_DURATION = int(get_env_variable("CACHE_EXTENSION_DURATION", 600))

# --- External Services ---
CALL_A_FRIEND_WEBHOOK_URL = get_env_variable("CALL_A_FRIEND_WEBHOOK_URL", required=True)

# --- Perform startup checks for required variables ---
# Calling get_env_variable with required=True handles this implicitly.
# You can add a simple function call here if you want an explicit startup log message.
def log_startup_config_check():
    logging.info("Configuration loaded. Required environment variables checked.")
    # Log non-sensitive config values if needed (use DEBUG level)
    logging.debug(f"GCP Project: {GCP_PROJECT_ID}")
    logging.debug(f"Cache TTL: {CACHE_TTL_SECONDS}s, Model: {GEMINI_MODEL_NAME}")

log_startup_config_check()