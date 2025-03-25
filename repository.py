import datetime
from datetime import timezone
from firebase_admin import firestore
from firebase_admin import credentials, initialize_app
from config import FIRESTORE_COLLECTION, ACTIVE_CACHE_DOC, ACTIVE_CACHE_FIELD, PREVIOUS_CACHE_FIELD, TRANSITION_UNTIL_FIELD, UPDATED_AT_FIELD, SYSTEM_PROMPT_DOC_PATH, SYSTEM_PROMPT_FIELD
import firebase_init

db = firestore.client()

def update_cache_config(active_cache, previous_cache, transition_until):
    """
    Update Firestore with new cache references and transition timestamp.
    """
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(ACTIVE_CACHE_DOC)
    data = {
        ACTIVE_CACHE_FIELD: active_cache,
        PREVIOUS_CACHE_FIELD: previous_cache,
        TRANSITION_UNTIL_FIELD: transition_until.isoformat(),
        UPDATED_AT_FIELD: datetime.datetime.now(timezone.utc).isoformat()
    }
    doc_ref.set(data)
    return data

def get_cache_config():
    """
    Retrieve the current cache configuration from Firestore.
    """
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(ACTIVE_CACHE_DOC)
    doc = doc_ref.get()
    if not doc.exists:
        return None
    return doc.to_dict()

def get_system_prompt():
    """
    Retrieve the system prompt from Firestore.
    The prompt should contain the placeholder "${inventory_data}".
    """
    doc_ref = db.document(SYSTEM_PROMPT_DOC_PATH)
    doc = doc_ref.get()
    if not doc.exists:
        return None
    data = doc.to_dict()
    return data.get(SYSTEM_PROMPT_FIELD)
