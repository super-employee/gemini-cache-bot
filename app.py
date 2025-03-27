import os
import time
import datetime
from datetime import timezone, timedelta
from flask import Flask, request, jsonify
from logger_config import setup_logger
import cache_service
import gemini_integration
import firebase_init  # Ensures Firebase is initialized
import repository
from config import EXPIRES_AT_FIELD, CACHE_EXTENSION_THRESHOLD, CACHE_EXTENSION_DURATION, ACTIVE_CACHE_FIELD

logger = setup_logger(__name__)

MAX_RETRIES = 6
INITIAL_DELAY = 1

app = Flask(__name__)

@app.route('/update_inventory', methods=['POST'])
def update_inventory():
    """HTTP endpoint to update inventory."""
    logger.info("Updating inventory.")
    try:
        new_cache_ref = cache_service.update_active_cache()
        logger.info("Inventory updated. New cache reference: %s", new_cache_ref)
        return jsonify({"new_cache": new_cache_ref}), 200
    except Exception:
        logger.exception("Failed to update inventory.")
        return jsonify({"error": "Internal server error."}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """Chat endpoint that processes user queries using the current active cache."""
    logger.info("Processing chat request.")
    data = request.get_json()
    if not data or "prompt" not in data:
        logger.warning("Chat request missing prompt.")
        return jsonify({"error": "No prompt provided."}), 400

    user_prompt = data.get("prompt")
    logger.info("User prompt received.")

    try:
        config = repository.get_cache_config()
        if config and config.get(EXPIRES_AT_FIELD):
            expires_at_str = config.get(EXPIRES_AT_FIELD)
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
            current_time = datetime.datetime.now(timezone.utc)
            time_left = expires_at - current_time
            if time_left.total_seconds() <= CACHE_EXTENSION_THRESHOLD:
                new_expires_at = expires_at + timedelta(seconds=CACHE_EXTENSION_DURATION)
                cache_service.extend_cache_expiration(new_expires_at=new_expires_at, cache_ref=config.get(ACTIVE_CACHE_FIELD))
                logger.info("Cache expiration extended.")
        else:
            logger.info("No cache configuration available for expiration check.")
    except Exception:
        logger.exception("Error processing cache configuration.")
        return jsonify({"error": "Internal server error."}), 500

    active_cache_ref = cache_service.get_active_cache()
    if not active_cache_ref:
        logger.error("Cache not initialized.")
        return jsonify({"error": "Cache not initialized. Please update inventory first."}), 500

    gemini_instance = gemini_integration.instantiate_model_from_cache(active_cache_ref)
    attempt = 0
    delay = INITIAL_DELAY

    while attempt < MAX_RETRIES:
        try:
            response = gemini_instance.generate_content(contents=user_prompt)
            break
        except Exception as e:
            if "429" in str(e):
                attempt += 1
                logger.warning("Rate limit encountered on attempt %d. Retrying in %d seconds...", attempt, delay)
                time.sleep(delay)
                delay *= 2
            else:
                logger.exception("Error generating content from Gemini.")
                return jsonify({"error": "Internal error occurred."}), 500
    else:
        logger.error("Maximum retry attempts reached for Gemini API.")
        return jsonify({"error": "Too many requests. Please try again later."}), 429

    logger.info("Chat processed successfully.")
    return jsonify({"response": response.text}), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", "8080"))
    logger.info("Starting API server on port %d", port)
    app.run(host='0.0.0.0', port=port, debug=False)
