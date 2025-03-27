import datetime
from datetime import timedelta
from typing import Optional

import vertexai
from vertexai.preview import caching
from vertexai.preview.generative_models import GenerativeModel, Part # Import Part

from config.config import (
    GEMINI_MODEL_NAME, GCP_PROJECT_ID, VERTEX_AI_REGION, LOG_LEVEL
)
from config.logger_config import setup_logger

logger = setup_logger(__name__, level=LOG_LEVEL)

# Define custom exceptions
class CacheCreationError(Exception):
    """Error during Gemini cache creation."""
    pass

class CacheInteractionError(Exception):
    """Error interacting with an existing Gemini cache."""
    pass


# --- Initialize Vertex AI ---
try:
    logger.info(f"Initializing Vertex AI SDK for project='{GCP_PROJECT_ID}', location='{VERTEX_AI_REGION}'")
    vertexai.init(project=GCP_PROJECT_ID, location=VERTEX_AI_REGION)
    logger.info("Vertex AI SDK initialized successfully.")
except Exception as e:
    logger.critical(f"CRITICAL: Failed to initialize Vertex AI SDK: {e}", exc_info=True)
    # Depending on application structure, might raise SystemExit or let callers handle
    raise RuntimeError("Vertex AI SDK initialization failed") from e

# --- Cache Operations ---

def create_cache(system_instruction: Part, contents: Part, ttl_seconds: int) -> str:
    """
    Creates a new Gemini context cache.

    Args:
        system_instruction: The system instruction as a GenerativeModel Part.
        contents: The content (e.g., inventory data) as a GenerativeModel Part.
        ttl_seconds: The time-to-live for the cache in seconds.

    Returns:
        The resource name (ID) of the created cache.

    Raises:
        CacheCreationError: If the cache creation fails.
        ValueError: If ttl_seconds is not positive.
    """
    if ttl_seconds <= 0:
        raise ValueError("CACHE_TTL_SECONDS must be a positive integer.")

    ttl_delta = timedelta(seconds=ttl_seconds)
    logger.info(f"Creating Gemini cache for model '{GEMINI_MODEL_NAME}' with TTL {ttl_delta}")

    try:
        new_cache = caching.CachedContent.create(
            model_name=GEMINI_MODEL_NAME,
            system_instruction=system_instruction,
            contents=[contents], # contents should be a list of Parts
            ttl=ttl_delta
        )
        logger.info(f"Gemini cache created successfully: {new_cache.name}")
        return new_cache.name
    except Exception as e:
        logger.error(f"Failed to create Gemini cache: {e}", exc_info=True)
        raise CacheCreationError(f"Failed to create Gemini cache: {e}") from e


def instantiate_model_from_cache(cache_ref: str) -> GenerativeModel:
    """
    Instantiates a GenerativeModel from an existing Gemini context cache reference.

    Args:
        cache_ref: The resource name (ID) of the cache (e.g., 7449974130461376512).

    Returns:
        An instance of GenerativeModel ready for use.

    Raises:
        CacheInteractionError: If the cache cannot be found or instantiation fails.
    """
    logger.info(f"Instantiating Gemini model from cache: {cache_ref}")
    try:
        # Validate cache_ref format crudely (optional)
        if not cache_ref or cache_ref.startswith("projects/"):
             raise ValueError(f"Invalid cache_ref format: {cache_ref}")

        cached_content = caching.CachedContent(cached_content_name=cache_ref)
        # Verify cache exists by trying to access a property (e.g., display_name or name)
        # This might incur an API call, but confirms validity.
        _ = cached_content.name # Access name to potentially trigger validation/fetch
        logger.debug(f"Cache object retrieved for {cache_ref}")

        model = GenerativeModel.from_cached_content(cached_content=cached_content)
        logger.info(f"Gemini model instantiated successfully from {cache_ref}")
        return model
    except ValueError as e: # Catch our format validation error
         logger.error(f"Invalid cache reference provided: {e}")
         raise CacheInteractionError(f"Invalid cache reference format: {cache_ref}") from e
    except Exception as e:
        # Catch specific Google API errors like NotFound if possible
        logger.error(f"Failed to instantiate model from cache '{cache_ref}': {e}", exc_info=True)
        # Check if error message indicates cache not found
        if "not found" in str(e).lower():
             raise CacheInteractionError(f"Gemini cache not found: {cache_ref}") from e
        else:
             raise CacheInteractionError(f"Failed to instantiate model from cache '{cache_ref}': {e}") from e


def extend_cache_ttl(cache_ref: str, ttl_seconds: int) -> None:
    """
    Updates the Time-To-Live (TTL) of an existing Gemini context cache.

    Args:
        cache_ref: The resource name (ID) of the cache to update.
        ttl_seconds: The new TTL duration in seconds (from now).

    Raises:
        CacheInteractionError: If updating the cache fails.
        ValueError: If ttl_seconds is not positive.
    """
    if ttl_seconds <= 0:
        raise ValueError("TTL extension duration (ttl_seconds) must be positive.")

    ttl_delta = timedelta(seconds=ttl_seconds)
    logger.info(f"Attempting to update TTL for cache '{cache_ref}' to {ttl_delta}")

    try:
        cached_content = caching.CachedContent(cached_content_name=cache_ref)
        cached_content.update(ttl=ttl_delta)
        # refresh() might not be needed if update() suffices, check SDK docs/behavior.
        # cached_content.refresh()
        logger.info(f"Successfully updated TTL for cache '{cache_ref}'")
    except Exception as e:
        logger.error(f"Failed to update TTL for cache '{cache_ref}': {e}", exc_info=True)
        if "not found" in str(e).lower():
             raise CacheInteractionError(f"Cannot extend TTL: Gemini cache not found: {cache_ref}") from e
        else:
             raise CacheInteractionError(f"Failed to update TTL for cache '{cache_ref}': {e}") from e

# Potential future function:
# def delete_cache(cache_ref: str) -> None: ...