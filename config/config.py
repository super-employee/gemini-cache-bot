import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Firestore settings
ACTIVE_CACHE_FIELD = os.getenv("ACTIVE_CACHE_FIELD", "activeCache")
UPDATED_AT_FIELD = os.getenv("UPDATED_AT_FIELD", "updatedAt")
EXPIRES_AT_FIELD = os.getenv("EXPIRES_AT_FIELD", "expiresAt")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
SERVICE_ACCOUNT_SECRET_ID = os.getenv("SERVICE_ACCOUNT_SECRET_ID")
SERVICE_ACCOUNT_SECRET_NAME = os.getenv("SERVICE_ACCOUNT_SECRET_NAME")

# System prompt settings in Firestore
SYSTEM_PROMPT_DOC_PATH = os.getenv("SYSTEM_PROMPT_DOC_PATH")
SYSTEM_PROMPT_FIELD = os.getenv("SYSTEM_PROMPT_FIELD", "prompt")

# Cache config settings in Firestore
CACHE_CONFIG_DOC_PATH = os.getenv("CACHE_CONFIG_DOC_PATH")

# Inventory data in Firestore
INVENTORY_DATA_DOC_PATH = os.getenv("INVENTORY_DATA_DOC_PATH")
INVENTORY_DATA_FIELD = os.getenv("INVENTORY_DATA_FIELD", "inventory")

# Gemini model (VertexAI) and cache settings
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-002")
CACHE_TTL = int(os.getenv("CACHE_TTL", 900))
VERTEX_AI_REGION = os.getenv("VERTEX_AI_REGION", "europe-southwest1")
CACHE_EXTENSION_THRESHOLD = int(os.getenv("CACHE_EXTENSION_THRESHOLD", 300))
CACHE_EXTENSION_DURATION = int(os.getenv("CACHE_EXTENSION_DURATION", 600))
