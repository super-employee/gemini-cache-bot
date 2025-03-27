import os
import time
import datetime
from datetime import timezone, timedelta
from flask import Flask, request, jsonify
from google.api_core.exceptions import ResourceExhausted  # Specific exception for 429

# Configuration and Initialization should happen before service imports
from config.config import (
    EXPIRES_AT_FIELD, CACHE_EXTENSION_THRESHOLD, CACHE_EXTENSION_DURATION,
    ACTIVE_CACHE_FIELD, LOG_LEVEL
)
from config.logger_config import setup_logger
import initializers.firebase_init  # Ensures Firebase is initialized before other modules use it

# Service imports
import services.cache_service as cache_service
import services.gemini_integration as gemini_integration
import services.repository as repository

logger = setup_logger(__name__, level=LOG_LEVEL)

MAX_RETRIES = 5 # Reduced slightly from 6 to avoid overly long waits
INITIAL_DELAY = 1 # seconds
BACKOFF_FACTOR = 2

app = Flask(__name__)

# Standardized Error Response Helper
def create_error_response(message, status_code, log_level="warning"):
    """Creates a standardized JSON error response and logs the error."""
    log_func = getattr(logger, log_level, logger.warning)
    log_func(message)
    return jsonify({"status": "error", "message": message}), status_code

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    # In a real scenario, you might check DB connection, etc.
    return jsonify({"status": "ok"}), 200

@app.route('/update_inventory', methods=['POST'])
def update_inventory():
    """
    HTTP endpoint to trigger a refresh of the inventory data and create a new cache.
    """
    logger.info("Received request to update inventory and cache.")
    try:
        # This function now handles getting inventory, creating cache, and updating config
        new_cache_ref = cache_service.force_update_active_cache()
        logger.info("Inventory and cache updated successfully. New cache reference: %s", new_cache_ref)
        return jsonify({"status": "success", "new_cache_ref": new_cache_ref}), 200
    except repository.InventoryDataError as e:
        return create_error_response(f"Inventory data error: {e}", 500, "error")
    except gemini_integration.CacheCreationError as e:
        return create_error_response(f"Failed to create Gemini cache: {e}", 500, "error")
    except Exception as e:
        # Log the full exception details for debugging
        logger.exception("An unexpected error occurred during inventory update.")
        return create_error_response("Internal server error during inventory update.", 500, "error")

@app.route('/chat', methods=['POST'])
def chat():
    """
    Chat endpoint that processes user queries using the current active cache.
    Handles cache retrieval, optional extension, and Gemini interaction.
    """
    logger.info("Received chat request.")
    data = request.get_json()
    if not data or "prompt" not in data:
        return create_error_response("Request body must be JSON and include a 'prompt' field.", 400)

    user_prompt = data["prompt"]
    if not isinstance(user_prompt, str) or not user_prompt.strip():
         return create_error_response("The 'prompt' field must be a non-empty string.", 400)

    logger.debug("User prompt received: %s", user_prompt) # Log prompt only at DEBUG level

    try:
        # --- Get Active Cache (Handles expiration check/update internally) ---
        active_cache_ref = cache_service.get_or_update_active_cache()
        if not active_cache_ref:
            # This occurs if config doesn't exist or update failed critically
            return create_error_response("Cache is not initialized or configuration is missing. Please try updating inventory.", 500, "error")
        logger.info("Using active cache: %s", active_cache_ref)

        # --- Optional: Check and Extend Cache Expiration if nearing threshold ---
        try:
            config = repository.get_cache_config() # Fetch config again to check expiry
            if config and config.get(EXPIRES_AT_FIELD):
                expires_at = datetime.datetime.fromisoformat(config[EXPIRES_AT_FIELD])
                current_time = datetime.datetime.now(timezone.utc)
                time_left_seconds = (expires_at - current_time).total_seconds()

                if 0 < time_left_seconds <= CACHE_EXTENSION_THRESHOLD:
                    logger.info(f"Cache nearing expiration ({time_left_seconds:.0f}s left). Attempting extension.")
                    # Calculate new expiration time based on *current* time + duration
                    new_expires_at = current_time + timedelta(seconds=CACHE_EXTENSION_DURATION)
                    # Extend in Firestore first, then Gemini
                    cache_service.extend_cache_expiration(new_expires_at=new_expires_at, cache_ref=active_cache_ref)
                    logger.info("Cache expiration potentially extended.")
                elif time_left_seconds <= 0:
                     # Should have been handled by get_or_update_active_cache, but log if seen
                     logger.warning("Cache appears expired even after get_or_update_active_cache. Proceeding, but check logic.")

        except Exception:
            # Log error during extension attempt but proceed with the current cache ref
            logger.exception("Error occurred during cache expiration check/extension attempt. Proceeding with current cache.")

        # --- Instantiate Gemini Model ---
        try:
            gemini_instance = gemini_integration.instantiate_model_from_cache(active_cache_ref)
        except Exception as e:
             logger.exception("Failed to instantiate Gemini model from cache ref: %s", active_cache_ref)
             return create_error_response("Failed to prepare AI model from cache.", 500, "error")

        # --- Generate Content with Retry Logic ---
        attempt = 0
        delay = INITIAL_DELAY
        response = None
        while attempt < MAX_RETRIES:
            try:
                logger.debug("Generating content from Gemini (Attempt %d)", attempt + 1)
                response = gemini_instance.generate_content(contents=user_prompt)
                logger.debug("Gemini response received.")
                # Basic safety/validity check
                if not response.candidates:
                    logger.warning("Gemini response received but contains no candidates.")
                    # Check for specific finish reasons if needed (e.g., safety)
                    # finish_reason = getattr(response.candidates[0], 'finish_reason', None)
                    # if finish_reason == ...: handle specific blocking
                    return create_error_response("AI model returned an empty or blocked response.", 500, "error")
                break # Success
            except ResourceExhausted as e: # Specific exception for 429
                attempt += 1
                if attempt >= MAX_RETRIES:
                    logger.error("Rate limit hit. Maximum retry attempts (%d) reached.", MAX_RETRIES)
                    return create_error_response("Rate limit exceeded. Please try again later.", 429, "error")
                logger.warning("Rate limit encountered (attempt %d/%d). Retrying in %d seconds...", attempt, MAX_RETRIES, delay)
                time.sleep(delay)
                delay *= BACKOFF_FACTOR
            except Exception as e:
                logger.exception("An unexpected error occurred during Gemini content generation.")
                return create_error_response("Internal error occurred during AI processing.", 500, "error")

        # --- Process and Return Response ---
        if response and response.candidates:
            # Accessing text safely, assuming the first candidate is the primary one
            response_text = response.candidates[0].content.parts[0].text
            logger.info("Chat processed successfully.")
            return jsonify({"status": "success", "response": response_text}), 200
        else:
             # Should have been caught earlier, but as a fallback
             logger.error("Failed to get a valid response from Gemini after retries.")
             return create_error_response("AI model failed to generate a response.", 500, "error")

    except Exception as e:
        # Catch-all for unexpected errors in the main flow
        logger.exception("An unexpected error occurred in the chat handler.")
        return create_error_response("An unexpected internal server error occurred.", 500, "error")

if __name__ == '__main__':
    port = int(os.getenv("PORT", "8080"))
    # Gunicorn controls the host and workers in production (via Dockerfile CMD)
    # debug=False is crucial for production
    logger.info(f"Starting Flask development server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)