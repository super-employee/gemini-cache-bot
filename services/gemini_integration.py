import datetime
from datetime import timezone
from typing import Optional

# Import the new SDK
from google import genai
from google.genai import types # Import types for config objects
from google.api_core import exceptions as google_exceptions

from config.config import (
    # GEMINI_MODEL_NAME will be passed to functions needing it
    GOOGLE_API_KEY,
    LOG_LEVEL
)
from config.logger_config import setup_logger

logger = setup_logger(__name__, level=LOG_LEVEL)

# --- Define custom exceptions ---
class GenAIConfigurationError(Exception):
    """Error configuring the GenAI client or API Key."""
    pass

class CacheCreationError(Exception):
    """Error during GenAI cache creation."""
    pass

class CacheInteractionError(Exception):
    """Error interacting (get, update, delete) with an existing GenAI cache."""
    pass

class GenAIGenerationError(Exception):
    """Error during content generation using the GenAI API."""
    pass


# --- Fetch API Key and Configure SDK Client at module load ---
try:
    
    if not GOOGLE_API_KEY:
        raise GenAIConfigurationError("Fetched Google AI API Key is empty.")

    # Create the client instance using the new SDK pattern
    # The client implicitly uses the API Key from env var if not passed,
    # but explicit passing is clearer.
    client = genai.Client(api_key=GOOGLE_API_KEY)
    logger.info("Google GenAI Client configured successfully.")

    # Optional: Verify client connection by listing models or similar
    # client.models.list()

except (google_exceptions.GoogleAPIError, ValueError, Exception) as e:
    logger.critical(f"CRITICAL: Failed to configure Google GenAI Client: {e}", exc_info=True)
    raise GenAIConfigurationError("Failed to configure Google GenAI Client.") from e

# --- Cache Operations ---

def create_cache(
    model_name: str,
    system_instruction: str,
    inventory_data: str,
    ttl_seconds: int,
    display_name: Optional[str] = None
) -> str:
    """
    Creates a new GenAI context cache using the google.genai SDK.

    Args:
        model_name: The specific model version (e.g., "models/gemini-1.5-flash-001").
                    Must support caching.
        system_instruction: The system prompt text.
        inventory_data: The inventory data text.
        ttl_seconds: The time-to-live for the cache in seconds.
        display_name: An optional name to identify the cache in listings.

    Returns:
        The resource name (ID) of the created cache (e.g., "cachedContents/xyz123").

    Raises:
        CacheCreationError: If the cache creation fails.
        ValueError: If ttl_seconds is not positive or model_name is invalid/unsupported.
    """
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be a positive integer.")
    if not model_name or not model_name.startswith("models/"):
         raise ValueError("Invalid model_name format. Must start with 'models/' and include version.")

    # Check if model supports caching (optional but recommended)
    # This requires an extra API call but prevents errors later
    try:
         model_info = client.models.get(model=model_name)
         if "createCachedContent" not in model_info.supported_actions:
              raise ValueError(f"Model '{model_name}' does not support context caching.")
         logger.debug(f"Model '{model_name}' supports caching.")
    except Exception as e:
         logger.warning(f"Could not verify caching support for model '{model_name}': {e}. Proceeding anyway.")
         # Or raise ValueError("Could not verify caching support for model.")

    ttl_str = f"{ttl_seconds}s"
    cache_display_name = display_name or f"cache-{model_name.split('/')[-1]}-{int(datetime.datetime.now(timezone.utc).timestamp())}"

    logger.info(f"Creating GenAI cache for model '{model_name}' with TTL {ttl_str}")

    try:
        # Construct the config dictionary or types.CreateCachedContentConfig object
        # Based on docs, using a dict for config seems common
        cache_config_dict = {
            'display_name': cache_display_name,
            'system_instruction': system_instruction,
            'contents': inventory_data, # Pass inventory data as content
            'ttl': ttl_str,
        }

        # Call create using the client, passing model and config
        created_cache = client.caches.create(
            model=model_name,
            config=types.CreateCachedContentConfig(**cache_config_dict)
        )

        logger.info(f"GenAI cache created successfully: Name='{created_cache.name}', DisplayName='{created_cache.display_name}'")
        logger.info(f"Cache Usage Metadata: {created_cache.usage_metadata}")

        # Check token count against minimum (32768 based on docs)
        min_tokens = 32768
        cached_tokens = getattr(created_cache.usage_metadata, 'total_token_count', 0)
        if cached_tokens < min_tokens:
            logger.warning(f"Created cache '{created_cache.name}' has {cached_tokens} tokens, which is below the recommended minimum of {min_tokens}.")
        elif cached_tokens == 0:
             logger.error(f"Cache '{created_cache.name}' reported 0 cached tokens. Content might be empty or invalid.")
             # Consider raising an error here if 0 tokens is always problematic
             # raise CacheCreationError(f"Cache creation resulted in 0 cached tokens for {created_cache.name}.")


        return created_cache.name # Return the resource name (e.g., cachedContents/...)

    except google_exceptions.InvalidArgument as e:
         if "less than minimum" in str(e).lower() or "token limit" in str(e).lower():
              logger.error(f"Failed to create cache: Content token count issue. Min required: {min_tokens}. Error: {e}", exc_info=True)
              raise CacheCreationError(f"Cache creation failed: Content token count issue (minimum {min_tokens} required).") from e
         elif "PERMISSION_DENIED" in str(e) or "API key not valid" in str(e):
              logger.critical(f"Permission denied or invalid API key during cache creation: {e}", exc_info=True)
              raise GenAIConfigurationError("Permission denied or invalid API Key for cache creation.") from e
         else:
              logger.error(f"Failed to create GenAI cache due to invalid argument: {e}", exc_info=True)
              raise CacheCreationError(f"Cache creation failed (Invalid Argument): {e}") from e
    except Exception as e:
        logger.error(f"Failed to create GenAI cache: {e}", exc_info=True)
        raise CacheCreationError(f"Cache creation failed: {e}") from e

def generate_content_with_cache(
    model_name: str,
    cache_name: str,
    user_prompt: str
) -> types.GenerateContentResponse:
    """
    Generates content using a previously created cache with the google.genai SDK.

    Args:
        model_name: The specific model version (e.g., "models/gemini-1.5-flash-001").
                     Must match the model used to create the cache.
        cache_name: The resource name of the cache (e.g., "cachedContents/xyz123").
        user_prompt: The user's query (this is the non-cached part of the prompt).

    Returns:
        The GenerateContentResponse object (a Pydantic model).

    Raises:
        GenAIGenerationError: If generation fails or content is blocked.
        CacheInteractionError: If the cache_name is invalid or not found.
        google_exceptions.ResourceExhausted: For rate limiting (caller should handle retry).
    """
    logger.debug(f"Generating content using cache '{cache_name}' with model '{model_name}'")
    try:
        # Construct the generation configuration pointing to the cache
        # Use types.GenerateContentConfig
        gen_config = {
            'cached_content' : cache_name
        }

        # Call generate_content using the client
        response = client.models.generate_content(
            model=model_name,
            contents=[user_prompt], # Only the user prompt goes here
            config=types.GenerateContentConfig(**gen_config)
        )

        logger.debug(f"Raw GenAI response received. Usage: {response.usage_metadata}")
        # Cached token count should appear in usage_metadata if successful

        # Check finish reason of the first candidate
        first_candidate = response.candidates[0]
        if first_candidate.finish_reason != types.FinishReason.STOP:
             logger.warning(f"Generation finished abnormally using cache '{cache_name}'. Reason: {first_candidate.finish_reason}")
             # Handle other finish reasons like MAX_TOKENS, SAFETY, RECITATION if needed
             if first_candidate.finish_reason == types.FinishReason.SAFETY:
                  # Redundant check if prompt_feedback already caught it, but good fallback
                  raise GenAIGenerationError(f"Response flagged for safety reasons. Cache: {cache_name}")


        logger.debug("Content generated successfully using cache.")
        return response

    except google_exceptions.NotFound as e:
         logger.error(f"Cache not found or invalid: {cache_name}. Error: {e}")
         raise CacheInteractionError(f"Cache not found or invalid: {cache_name}") from e
    except google_exceptions.InvalidArgument as e:
         logger.error(f"Invalid argument using cache '{cache_name}': {e}")
         # Could be model mismatch, invalid cache name format, etc.
         raise CacheInteractionError(f"Invalid argument using cache '{cache_name}': {e}") from e
    except google_exceptions.ResourceExhausted as e:
        logger.warning(f"Rate limit likely hit using cache '{cache_name}': {e}")
        raise # Let caller handle retry
    except GenAIGenerationError: # Re-raise safety block error
        raise
    except Exception as e:
        logger.error(f"Unexpected error during GenAI generation with cache '{cache_name}': {e}", exc_info=True)
        raise GenAIGenerationError(f"Unexpected error during generation with cache '{cache_name}': {e}") from e


def extend_cache_expiry(cache_name: str, new_expiry_time: datetime.datetime) -> None:
    """
    Updates the expiration time of an existing GenAI context cache.

    Args:
        cache_name: The resource name (ID) of the cache to update (e.g., "cachedContents/xyz123").
        new_expiry_time: The new absolute expiration time (must be timezone-aware UTC).

    Raises:
        CacheInteractionError: If updating the cache fails (e.g., not found).
        ValueError: If new_expiry_time is not timezone-aware UTC.
    """
    if new_expiry_time.tzinfo is None or new_expiry_time.tzinfo.utcoffset(new_expiry_time) != datetime.timedelta(0):
        raise ValueError("new_expiry_time must be timezone-aware and in UTC.")

    logger.info(f"Attempting to update expiry for cache '{cache_name}' to {new_expiry_time.isoformat()}")

    try:
        # Use types.UpdateCachedContentConfig
        update_config = types.UpdateCachedContentConfig(expire_time=new_expiry_time)
        # Call update using the client
        client.caches.update(name=cache_name, config=update_config)
        logger.info(f"Successfully updated expiry for cache '{cache_name}'")
    except google_exceptions.NotFound as e:
        logger.error(f"Cannot update expiry: Cache not found: {cache_name}. Error: {e}")
        raise CacheInteractionError(f"Cannot update expiry: Cache not found: {cache_name}") from e
    except google_exceptions.InvalidArgument as e:
         logger.error(f"Invalid argument updating expiry for cache '{cache_name}': {e}")
         raise CacheInteractionError(f"Invalid argument updating expiry for cache '{cache_name}': {e}") from e
    except Exception as e:
        logger.error(f"Failed to update expiry for cache '{cache_name}': {e}", exc_info=True)
        raise CacheInteractionError(f"Failed to update expiry for cache '{cache_name}': {e}") from e


def delete_cache(cache_name: str) -> None:
    """
    Deletes a GenAI context cache using the google.genai SDK.

    Args:
        cache_name: The resource name (ID) of the cache to delete (e.g., "cachedContents/xyz123").

    Raises:
        CacheInteractionError: If deleting the cache fails unexpectedly.
    """
    logger.info(f"Attempting to delete cache: {cache_name}")
    try:
        # Call delete using the client
        client.caches.delete(name=cache_name)
        logger.info(f"Successfully deleted cache: {cache_name}")
    except google_exceptions.NotFound as e:
        # Deleting a non-existent cache is often okay, just log it.
        logger.warning(f"Attempted to delete non-existent cache: {cache_name}. Error: {e}")
        # No exception raised here, treat as success (idempotent delete)
    except Exception as e:
        logger.error(f"Failed to delete cache '{cache_name}': {e}", exc_info=True)
        raise CacheInteractionError(f"Failed to delete cache '{cache_name}': {e}") from e