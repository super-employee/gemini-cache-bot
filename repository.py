import datetime
from datetime import timezone, timedelta
from firebase_admin import firestore
from firebase_admin import credentials, initialize_app
from config import (
    ACTIVE_CACHE_FIELD, 
    UPDATED_AT_FIELD,
    EXPIRES_AT_FIELD,
    CACHE_CONFIG_DOC_PATH,
    CACHE_TTL, 
    SYSTEM_PROMPT_DOC_PATH, 
    SYSTEM_PROMPT_FIELD,
    INVENTORY_DATA_DOC_PATH,
    INVENTORY_DATA_FIELD
)
import firebase_init  # Ensures Firebase is initialized

db = firestore.client()

def update_cache_config(active_cache):
    """
    Update Firestore with new cache configuration.
    Sets active cache and the expiration time (current time + CACHE_TTL - 10 seconds).
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    data = {
        ACTIVE_CACHE_FIELD: active_cache,
        UPDATED_AT_FIELD: datetime.datetime.now(timezone.utc).isoformat(),
        EXPIRES_AT_FIELD: (
            datetime.datetime.now(timezone.utc) + timedelta(seconds=int(CACHE_TTL)) - timedelta(seconds=10)
        ).isoformat()
    }
    print(f"[DEBUG] Updating cache configs with data:")
    print(data)
    doc_ref.set(data)
    print("[DEBUG] Cache config update complete.")
    return data

def get_cache_config():
    """
    Retrieve the current cache configuration from Firestore.
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    print(f"[DEBUG] Retrieving cache config from document '{CACHE_CONFIG_DOC_PATH}'.")
    doc = doc_ref.get()
    if not doc.exists:
        print("[DEBUG] No cache config document found.")
        return None
    config = doc.to_dict()
    print("[DEBUG] Retrieved cache config:", config)
    return config

def get_system_prompt():
    """
    Retrieve the system prompt from Firestore.
    The prompt should contain the placeholder "${inventory_data}".
    """
    print(f"[DEBUG] Retrieving system prompt from document path '{SYSTEM_PROMPT_DOC_PATH}'.")
    doc_ref = db.document(SYSTEM_PROMPT_DOC_PATH)
    doc = doc_ref.get()
    if not doc.exists:
        print("[DEBUG] System prompt document not found.")
        return None
    data = doc.to_dict()
    prompt = data.get(SYSTEM_PROMPT_FIELD)
    print(f"[DEBUG] Retrieved system prompt.")
    return prompt

def get_inventory_data():
    """
    Retrieve the inventory data from Firestore.
    """
    print(f"[DEBUG] Retrieving inventory data from document path '{INVENTORY_DATA_DOC_PATH}'.")
    doc_ref = db.document(INVENTORY_DATA_DOC_PATH)
    doc = doc_ref.get()
    if not doc.exists:
        print("[DEBUG] Inventory data document not found.")
        return None
    data = doc.to_dict()
    inventory_data = data.get(INVENTORY_DATA_FIELD)
    print("[DEBUG] Retrieved inventory data.")
    return inventory_data

def extend_cache_expiration(new_expires_at):
    """
    Extend the cache expiration in the cache configuration document.
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    update_data = {
        EXPIRES_AT_FIELD: new_expires_at.isoformat(),
        UPDATED_AT_FIELD: datetime.datetime.now(timezone.utc).isoformat()
    }
    print(f"[DEBUG] Extending cache expiration to {new_expires_at.isoformat()}.")
    doc_ref.update(update_data)
    print("[DEBUG] Cache expiration extended.")
    return update_data
