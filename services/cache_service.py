import datetime
from datetime import timezone, timedelta
from typing import Optional, Tuple

from config.config import (
    ACTIVE_CACHE_FIELD, EXPIRES_AT_FIELD, CACHE_TTL_SECONDS,
    LOG_LEVEL, GEMINI_MODEL_NAME
)
import services.repository as repository
import services.gemini_integration as gemini_integration
from config.logger_config import setup_logger
from google.api_core import exceptions as google_exceptions

from google import genai
from google.genai import types

# Import the function declaration from gemini_integration
from services.gemini_integration import REQUEST_COLLEAGUE_HELP_DECLARATION

logger = setup_logger(__name__, level=LOG_LEVEL)

# Define custom exceptions for clarity
class CacheUpdateError(Exception):
    """Custom exception for errors during cache update."""
    pass

class CacheResponseError(Exception):
    """Custom exception for errors when attempting to use the cache to generate a response."""
    pass

def _create_new_gemini_cache(inventory_data: str) -> str:
    """
    Creates a new Gemini cache with system prompt, inventory data, and defined tools.
    """
    logger.info("Preparing to create a new Gemini cache.")
    try:
        system_instruction_text = repository.get_system_prompt()
        if system_instruction_text is None:
            logger.error("System prompt not found in Firestore. Cannot create cache.")
            raise repository.SystemPromptError("System prompt not found, cannot create cache.")
    except Exception as e:
        logger.error(f"Failed to retrieve system prompt: {e}")
        raise repository.SystemPromptError("Could not retrieve system prompt for cache creation.") from e

    # --- Define the Tools to be included in the cache ---
    call_friend_tool = types.Tool(
        function_declarations=[REQUEST_COLLEAGUE_HELP_DECLARATION]
    )
    tools_list = [call_friend_tool]
    logger.info("Defining tools to be included in the new cache.")

    logger.info("Calling Gemini API to create cache...")
    try:
        new_cache_ref = gemini_integration.create_cache(
            model_name=GEMINI_MODEL_NAME,
            system_instruction=system_instruction_text,
            inventory_data=inventory_data,
            ttl_seconds=CACHE_TTL_SECONDS,
            tools=tools_list # <-- Pass the defined tools here
        )
        logger.info("Successfully created new Gemini cache: %s", new_cache_ref)
        return new_cache_ref
    # ... (exception handling remains the same) ...
    except Exception as e:
        logger.error(f"Gemini cache creation failed: {e}", exc_info=True)
        raise gemini_integration.CacheCreationError("Gemini API call failed during cache creation.") from e

def force_update_active_cache() -> str:
    """
    Retrieves latest inventory, creates a new Gemini cache, and updates
    the Firestore configuration to point to the new cache.

    This function bypasses expiration checks and always creates a new cache.

    Returns:
        The name (resource ID) of the new active cache.

    Raises:
        repository.InventoryDataError: If inventory data cannot be retrieved.
        repository.SystemPromptError: If system prompt cannot be retrieved.
        gemini_integration.CacheCreationError: If Gemini cache creation fails.
        repository.ConfigUpdateError: If Firestore config update fails.
        CacheUpdateError: For general failures in the update process.
    """
    logger.info("Forcing update of active cache.")
    try:
        inventory_data = repository.get_inventory_data()
        if inventory_data is None:
             logger.error("Inventory data is missing or could not be retrieved.")
             raise repository.InventoryDataError("Inventory data not found or empty.")

        # Proceed to create the new cache
        new_cache_ref = _create_new_gemini_cache(inventory_data)

        # Update Firestore configuration with the new cache reference and expiry
        repository.update_cache_config(active_cache=new_cache_ref)
        logger.info("Successfully updated Firestore with new active cache reference.")

        return new_cache_ref

    # Propagate specific errors upwards
    except (repository.InventoryDataError, repository.SystemPromptError,
            gemini_integration.CacheCreationError, repository.ConfigUpdateError) as e:
        logger.error(f"Failed to force update cache due to: {e}", exc_info=True)
        raise # Re-raise the specific exception

    except Exception as e:
        logger.exception("An unexpected error occurred during forced cache update.")
        raise CacheUpdateError("Unexpected error during forced cache update.") from e

def generate_content_from_cache(user_prompt: str) -> types.GenerateContentResponse:
    """
    Gets the active cache and calls Gemini to generate content using that cache.
    The cache already contains system instructions and tools.
    Handles the function calling loop internally via gemini_integration.
    """
    active_cache_ref = get_or_update_active_cache()
    if not active_cache_ref:
        logger.error("Active cache reference is None. Cannot generate content.")
        raise CacheResponseError("Active cache reference is None. Cannot generate content.")

    try:
        # --- Define the Tools ---
        # REMOVED: Tools are no longer defined here, they are in the cache.
        # call_friend_tool = types.Tool(...)
        # tools_list = [call_friend_tool]

        # --- Call Gemini Integration (which now handles the function call loop) ---
        response = gemini_integration.generate_content_with_cache(
            model_name=GEMINI_MODEL_NAME, # Still need model name for the call
            cache_name=active_cache_ref,
            user_prompt=user_prompt
            # tools=tools_list # <-- REMOVE passing tools here
        )
        return response

    # ... (exception handling remains the same) ...
    except gemini_integration.GenAIGenerationError as e:
        logger.error(f"Error generating content from cache via Gemini: {e}")
        raise CacheResponseError(f"AI generation failed: {e}") from e
    except gemini_integration.CacheInteractionError as e:
         logger.error(f"Error interacting with Gemini cache '{active_cache_ref}': {e}")
         raise CacheResponseError(f"AI cache interaction failed: {e}") from e
    except Exception as e:
        logger.exception("An unexpected error occurred while trying to generate content from cache.")
        if isinstance(e, google_exceptions.ResourceExhausted):
            raise
        raise CacheResponseError("Unexpected error during content generation from cache.") from e
    
def get_or_update_active_cache() -> Optional[str]:
    """
    Retrieves the active cache reference from Firestore. If the cache is
    expired based on Firestore's 'expiresAt' field, triggers an update
    to create a new cache and updates Firestore.

    Returns:
        The active cache reference string, or None if configuration is missing
        or a critical update error occurs.

    Note:
        This implementation does not use locking. Concurrent requests might trigger
        multiple cache updates if they hit the expiration boundary simultaneously.
        Consider Firestore transactions for a more robust solution if needed.
    """
    logger.info("Retrieving or updating active cache reference.")
    try:
        config = repository.get_cache_config()
        if not config:
            logger.error("Cache configuration not found in Firestore.")
            return None

        active_cache_ref = config.get(ACTIVE_CACHE_FIELD)
        expires_at_str = config.get(EXPIRES_AT_FIELD)

        if not active_cache_ref:
             logger.warning("Active cache reference field is missing in config. Triggering update.")
             try:
                 return force_update_active_cache()
             except Exception:
                logger.exception("Failed to update cache after finding missing reference.")
                return None # Indicate critical failure

        if not expires_at_str:
            logger.warning("Cache expiration field is missing in config. Assuming expired, triggering update.")
            try:
                 return force_update_active_cache()
            except Exception:
                logger.exception("Failed to update cache after finding missing expiration.")
                return None # Indicate critical failure

        # Check expiration
        try:
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
            current_time = datetime.datetime.now(timezone.utc)

            if current_time >= expires_at:
                logger.info("Cache expired (based on Firestore config). Triggering update.")
                # --- Potential Race Condition Point ---
                # Multiple requests might execute force_update_active_cache here concurrently.
                # The last one to update Firestore 'wins'. Wasted Gemini calls possible.
                # TODO: Implement locking (e.g., Firestore transaction) if this becomes an issue.
                try:
                    return force_update_active_cache()
                except Exception:
                    logger.exception("Failed to update expired cache. Returning potentially stale ref.")
                    # Decide whether to return the stale ref or None. Returning stale might
                    # still work if Gemini's TTL is slightly longer, but risks errors.
                    # Returning None forces an error upstream. Let's return None for safety.
                    return None
            else:
                # Cache is still valid
                logger.info("Active cache reference is valid.")
                return active_cache_ref

        except ValueError:
            logger.error(f"Invalid format for expiration timestamp in config: '{expires_at_str}'. Assuming expired.")
            try:
                 return force_update_active_cache()
            except Exception:
                logger.exception("Failed to update cache after finding invalid expiration format.")
                return None

    except Exception as e:
        logger.exception("An unexpected error occurred while getting or updating cache.")
        return None


def extend_cache_expiration(new_expires_at: datetime.datetime, cache_ref: str) -> None:
    """
    Extends the cache expiration both in Firestore and attempts to update
    the Gemini cache TTL. Updates Firestore first.

    Args:
        new_expires_at: The new expiration timestamp (timezone-aware UTC).
        cache_ref: The Gemini cache reference string to extend.

    Raises:
        repository.ConfigUpdateError: If updating Firestore fails.
        Logs warnings if Gemini TTL update fails but does not raise an error for it.
    """
    logger.info(f"Attempting to extend cache expiration to {new_expires_at.isoformat()} for {cache_ref}")

    try:
        # 1. Update Firestore first
        repository.update_cache_expiration(new_expires_at=new_expires_at)
        logger.info("Successfully updated cache expiration in Firestore.")

        # 2. Attempt to update Gemini TTL (best effort)
        try:
            # Calculate remaining TTL from now until new_expires_at for Gemini update
            # Ensure TTL is positive
            remaining_ttl = max(0, (new_expires_at - datetime.datetime.now(timezone.utc)).total_seconds())
            if remaining_ttl > 0:
                 # Add a small buffer (e.g., 10s) to ensure Gemini TTL >= Firestore expiry
                 gemini_ttl_seconds = int(remaining_ttl + 10)
                 gemini_integration.extend_cache_ttl(cache_ref=cache_ref, ttl_seconds=gemini_ttl_seconds)
                 logger.info(f"Successfully requested Gemini cache TTL extension for {cache_ref} to ~{gemini_ttl_seconds}s.")
            else:
                 logger.warning(f"Calculated remaining TTL for Gemini is zero or negative for {cache_ref}. Skipping Gemini TTL update.")

        except Exception as gemini_e:
             # Log the error but don't fail the whole operation if only Gemini update fails
             logger.warning(f"Failed to extend Gemini cache TTL for {cache_ref}: {gemini_e}", exc_info=True)

    except repository.ConfigUpdateError as firestore_e:
         # If Firestore update fails, re-raise the specific error
         logger.error(f"Failed to update cache expiration in Firestore: {firestore_e}")
         raise
    except Exception as e:
        # Catch any other unexpected errors during the extension process
        logger.exception(f"An unexpected error occurred during cache extension for {cache_ref}")
        # Depending on policy, you might want to raise a generic error here too