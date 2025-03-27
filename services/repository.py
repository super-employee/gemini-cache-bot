import datetime
from datetime import timezone, timedelta
from typing import Optional, Dict, Any

from firebase_admin import firestore
from google.cloud import firestore as google_firestore # For types if needed
from google.api_core import exceptions as google_exceptions

from config.config import (
    ACTIVE_CACHE_FIELD,
    UPDATED_AT_FIELD,
    EXPIRES_AT_FIELD,
    CACHE_CONFIG_DOC_PATH,
    CACHE_TTL_SECONDS,
    SYSTEM_PROMPT_DOC_PATH,
    SYSTEM_PROMPT_FIELD,
    INVENTORY_DATA_DOC_PATH,
    INVENTORY_DATA_FIELD,
    LOG_LEVEL
)
# Ensure Firebase is initialized before this module's functions are called
import initializers.firebase_init # noqa: F401 - Imports for initialization side effects

from config.logger_config import setup_logger

logger = setup_logger(__name__, level=LOG_LEVEL)

# Define custom exceptions for repository operations
class ConfigNotFoundError(Exception):
    """Firestore configuration document not found."""
    pass

class ConfigUpdateError(Exception):
    """Error updating Firestore configuration."""
    pass

class SystemPromptError(Exception):
    """Error retrieving system prompt from Firestore."""
    pass

class InventoryDataError(Exception):
    """Error retrieving inventory data from Firestore."""
    pass


# Get Firestore client instance
try:
    db = firestore.client()
    logger.info("Firestore client obtained successfully.")
except Exception as e:
    logger.critical(f"CRITICAL: Failed to get Firestore client: {e}", exc_info=True)
    # Application likely cannot function without Firestore
    raise RuntimeError("Failed to initialize Firestore client") from e


def update_cache_config(active_cache: str) -> Dict[str, Any]:
    """
    Sets the cache configuration document in Firestore with the new active cache
    reference and calculates the new expiration time based on CACHE_TTL_SECONDS.

    Args:
        active_cache: The resource name (ID) of the new active Gemini cache.

    Returns:
        The data dictionary that was written to Firestore.

    Raises:
        ConfigUpdateError: If the Firestore operation fails.
        ValueError: If active_cache is empty.
    """
    if not active_cache:
        raise ValueError("active_cache reference cannot be empty.")

    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    now = datetime.datetime.now(timezone.utc)
    # Calculate expiration correctly based on TTL from now
    expires_at = now + timedelta(seconds=CACHE_TTL_SECONDS)

    data = {
        ACTIVE_CACHE_FIELD: active_cache,
        UPDATED_AT_FIELD: now.isoformat(),
        EXPIRES_AT_FIELD: expires_at.isoformat()
    }
    logger.info(f"Setting Firestore cache config: {CACHE_CONFIG_DOC_PATH} with data: { {**data, ACTIVE_CACHE_FIELD: '...'+active_cache[-10:]} }") # Log truncated ref

    try:
        doc_ref.set(data, merge=False) # Overwrite the document completely
        logger.info("Firestore cache config updated successfully.")
        return data
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Firestore error setting cache config at {CACHE_CONFIG_DOC_PATH}: {e}", exc_info=True)
        raise ConfigUpdateError(f"Firestore API error updating config: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error setting cache config at {CACHE_CONFIG_DOC_PATH}: {e}", exc_info=True)
        raise ConfigUpdateError(f"Unexpected error updating config: {e}") from e


def update_cache_expiration(new_expires_at: datetime.datetime) -> Dict[str, str]:
    """
    Updates only the expiration and updated_at fields in the Firestore
    cache configuration document.

    Args:
        new_expires_at: The new timezone-aware UTC expiration timestamp.

    Returns:
        The data dictionary used for the update.

    Raises:
        ConfigUpdateError: If the Firestore operation fails or doc doesn't exist.
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    now_iso = datetime.datetime.now(timezone.utc).isoformat()
    expires_at_iso = new_expires_at.isoformat()

    update_data = {
        EXPIRES_AT_FIELD: expires_at_iso,
        UPDATED_AT_FIELD: now_iso
    }
    logger.info(f"Updating Firestore cache expiration: {CACHE_CONFIG_DOC_PATH} to {expires_at_iso}")

    try:
        # Use update - fails if the document doesn't exist
        doc_ref.update(update_data)
        logger.info("Firestore cache expiration updated successfully.")
        return update_data
    except google_exceptions.NotFound:
         logger.error(f"Cache config document not found at {CACHE_CONFIG_DOC_PATH} during expiration update.")
         raise ConfigUpdateError(f"Cannot update expiration: Config document not found at {CACHE_CONFIG_DOC_PATH}")
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Firestore error updating cache expiration at {CACHE_CONFIG_DOC_PATH}: {e}", exc_info=True)
        raise ConfigUpdateError(f"Firestore API error updating expiration: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error updating cache expiration at {CACHE_CONFIG_DOC_PATH}: {e}", exc_info=True)
        raise ConfigUpdateError(f"Unexpected error updating expiration: {e}") from e


def get_cache_config() -> Optional[Dict[str, Any]]:
    """
    Retrieves the current cache configuration document from Firestore.

    Returns:
        A dictionary containing the configuration, or None if the document
        does not exist or an error occurs.
    """
    doc_ref = db.document(CACHE_CONFIG_DOC_PATH)
    logger.debug(f"Retrieving cache configuration from Firestore: {CACHE_CONFIG_DOC_PATH}")
    try:
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
            logger.warning(f"Cache config document does not exist at: {CACHE_CONFIG_DOC_PATH}")
            return None
        config = doc_snapshot.to_dict()
        logger.debug("Cache configuration retrieved successfully.")
        return config
    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Firestore error retrieving cache config from {CACHE_CONFIG_DOC_PATH}: {e}", exc_info=True)
        return None # Treat API errors as config not available for robustness
    except Exception as e:
        logger.error(f"Unexpected error retrieving cache config from {CACHE_CONFIG_DOC_PATH}: {e}", exc_info=True)
        return None


def get_system_prompt() -> Optional[str]:
    """
    Retrieves the system prompt string from its configured Firestore document.

    Returns:
        The system prompt string, or None if the document or field is not found
        or an error occurs.

    Raises:
        SystemPromptError: If a Firestore API error occurs during retrieval.
    """
    doc_ref = db.document(SYSTEM_PROMPT_DOC_PATH)
    logger.debug(f"Retrieving system prompt from Firestore: {SYSTEM_PROMPT_DOC_PATH}")
    try:
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
            logger.warning(f"System prompt document not found at: {SYSTEM_PROMPT_DOC_PATH}")
            return None

        data = doc_snapshot.to_dict()
        prompt = data.get(SYSTEM_PROMPT_FIELD)

        if prompt is None:
            logger.warning(f"Field '{SYSTEM_PROMPT_FIELD}' not found in document: {SYSTEM_PROMPT_DOC_PATH}")
            return None
        if not isinstance(prompt, str):
             logger.warning(f"Field '{SYSTEM_PROMPT_FIELD}' in {SYSTEM_PROMPT_DOC_PATH} is not a string.")
             return None # Or raise error? Return None for now.

        logger.debug("System prompt retrieved successfully.")
        return prompt.strip() if prompt else None

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Firestore error retrieving system prompt from {SYSTEM_PROMPT_DOC_PATH}: {e}", exc_info=True)
        raise SystemPromptError(f"Firestore API error retrieving system prompt: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error retrieving system prompt from {SYSTEM_PROMPT_DOC_PATH}: {e}", exc_info=True)
        # Don't raise SystemPromptError for unexpected errors, let caller handle generic Exception
        # Or potentially define a different error type? For now, return None.
        return None


def get_inventory_data() -> Optional[str]:
    """
    Retrieves the inventory data string from its configured Firestore document.

    Returns:
        The inventory data string, or None if the document or field is not found,
        the field is not a string, or an error occurs.

    Raises:
        InventoryDataError: If a Firestore API error occurs during retrieval.
    """
    doc_ref = db.document(INVENTORY_DATA_DOC_PATH)
    logger.debug(f"Retrieving inventory data from Firestore: {INVENTORY_DATA_DOC_PATH}")
    try:
        doc_snapshot = doc_ref.get()
        if not doc_snapshot.exists:
            logger.warning(f"Inventory data document not found at: {INVENTORY_DATA_DOC_PATH}")
            return None

        data = doc_snapshot.to_dict()
        inventory_data = data.get(INVENTORY_DATA_FIELD)

        if inventory_data is None:
            logger.warning(f"Field '{INVENTORY_DATA_FIELD}' not found in document: {INVENTORY_DATA_DOC_PATH}")
            return None
        if not isinstance(inventory_data, str):
             logger.error(f"Inventory data field '{INVENTORY_DATA_FIELD}' in {INVENTORY_DATA_DOC_PATH} is not a string.")
             # This might be a critical data format error
             raise InventoryDataError(f"Inventory data field '{INVENTORY_DATA_FIELD}' is not a string.")

        # Consider adding a check for empty string if that's invalid
        # if not inventory_data.strip():
        #     logger.warning(f"Inventory data field '{INVENTORY_DATA_FIELD}' is empty.")
        #     return None # Or raise error?

        logger.debug("Inventory data retrieved successfully.")
        return inventory_data # Return as is, let caller handle format

    except google_exceptions.GoogleAPIError as e:
        logger.error(f"Firestore error retrieving inventory data from {INVENTORY_DATA_DOC_PATH}: {e}", exc_info=True)
        raise InventoryDataError(f"Firestore API error retrieving inventory data: {e}") from e
    except InventoryDataError: # Re-raise the specific error caught above
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving inventory data from {INVENTORY_DATA_DOC_PATH}: {e}", exc_info=True)
        return None # Return None for unexpected errors