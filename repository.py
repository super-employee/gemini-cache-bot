import datetime
from datetime import timezone, timedelta
from firebase_admin import firestore
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
from logger_config import setup_logger

logger = setup_logger(__name__)

db = firestore.client()

def update_cache_config(active_cache):
    """
    Update Firestore with new cache configuration.
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    data = {
        ACTIVE_CACHE_FIELD: active_cache,
        UPDATED_AT_FIELD: datetime.datetime.now(timezone.utc).isoformat(),
        EXPIRES_AT_FIELD: (
            datetime.datetime.now(timezone.utc) + timedelta(seconds=int(CACHE_TTL)) - timedelta(seconds=10)
        ).isoformat()
    }
    logger.info("Updating cache config in Firestore.")
    doc_ref.set(data)
    logger.info("Cache config updated.")
    return data

def get_cache_config():
    """
    Retrieve the current cache configuration from Firestore.
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    logger.info("Retrieving cache configuration from Firestore.")
    doc = doc_ref.get()
    if not doc.exists:
        logger.warning("Cache config document does not exist.")
        return None
    config = doc.to_dict()
    logger.info("Cache configuration retrieved.")
    return config

def get_system_prompt():
    """
    Retrieve the system prompt from Firestore.
    """
    logger.info("Retrieving system prompt from Firestore.")
    doc_ref = db.document(SYSTEM_PROMPT_DOC_PATH)
    doc = doc_ref.get()
    if not doc.exists:
        logger.warning("System prompt document not found.")
        return None
    data = doc.to_dict()
    prompt = data.get(SYSTEM_PROMPT_FIELD)
    logger.info("System prompt retrieved.")
    return prompt

def get_inventory_data():
    """
    Retrieve the inventory data from Firestore.
    """
    logger.info("Retrieving inventory data from Firestore.")
    doc_ref = db.document(INVENTORY_DATA_DOC_PATH)
    doc = doc_ref.get()
    if not doc.exists:
        logger.warning("Inventory data document not found.")
        return None
    data = doc.to_dict()
    inventory_data = data.get(INVENTORY_DATA_FIELD)
    logger.info("Inventory data retrieved.")
    return inventory_data

def extend_cache_expiration(new_expires_at):
    """
    Extend the cache expiration in Firestore.
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    update_data = {
        EXPIRES_AT_FIELD: new_expires_at.isoformat(),
        UPDATED_AT_FIELD: datetime.datetime.now(timezone.utc).isoformat()
    }
    logger.info("Extending cache expiration in Firestore to %s", new_expires_at.isoformat())
    doc_ref.update(update_data)
    logger.info("Cache expiration extended in Firestore.")
    return update_data
