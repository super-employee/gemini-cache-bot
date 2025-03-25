import os
from dotenv import load_dotenv

load_dotenv(override=True)  # Load environment variables

# Firestore settings
FIRESTORE_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "cacheConfigs")
ACTIVE_CACHE_DOC = os.getenv("ACTIVE_CACHE_DOC", "active")
ACTIVE_CACHE_FIELD=os.getenv("ACTIVE_CACHE_FIELD", "activeCache")
PREVIOUS_CACHE_FIELD=os.getenv("PREVIOUS_CACHE_FIELD", "previousCache")
TRANSITION_UNTIL_FIELD=os.getenv("TRANSITION_UNTIL_FIELD", "transitionUntil")
UPDATED_AT_FIELD=os.getenv("UPDATED_AT_FIELD", "updatedAt")
GCP_PROJECT_ID=os.getenv("GCP_PROJECT_ID")
SERVICE_ACCOUNT_SECRET_ID=os.getenv("SERVICE_ACCOUNT_SECRET_ID")
SERVICE_ACCOUNT_SECRET_NAME=os.getenv("SERVICE_ACCOUNT_SECRET_NAME")

# System prompt settings in Firestore
SYSTEM_PROMPT_DOC_PATH = os.getenv("SYSTEM_PROMPT_DOC_PATH","")
SYSTEM_PROMPT_FIELD = os.getenv("SYSTEM_PROMPT_FIELD", "prompt")

# Transition period in seconds for a seamless cache switch
TRANSITION_PERIOD_SECONDS = int(os.getenv("TRANSITION_PERIOD_SECONDS", "30"))

# Gemini model and cache settings
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-002")
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # in seconds
