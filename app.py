import os
import time
import datetime
from datetime import timezone, timedelta
from flask import Flask, request, jsonify
import cache_service
import gemini_integration
import firebase_init  # Ensures Firebase is initialized
import repository  # Needed for accessing cache config
from config import EXPIRES_AT_FIELD, CACHE_EXTENSION_THRESHOLD, CACHE_EXTENSION_DURATION, ACTIVE_CACHE_FIELD

# Define maximum number of retries and the initial delay (in seconds)
MAX_RETRIES = 6
INITIAL_DELAY = 1

app = Flask(__name__)

@app.route('/update_inventory', methods=['POST'])
def update_inventory():
    """
    HTTP endpoint to update inventory.
    """
    print("Received request to update inventory.")
    new_cache_ref = cache_service.update_active_cache()
    print("New cache reference obtained:", new_cache_ref)
    return jsonify({"new_cache": new_cache_ref}), 200

@app.route('/chat', methods=['POST'])
def chat():
    """
    Chat endpoint that processes user queries using the current active cache.
    If the cache expiration is within 5 minutes, it extends the expiration by 5 minutes.
    """
    print("Received chat request.")
    data = request.get_json()
    print("Chat request JSON:", data)
    user_prompt = data.get("prompt")
    if not user_prompt:
        print("No prompt provided in the chat request.")
        return jsonify({"error": "No prompt provided."}), 400
    print("User prompt:", user_prompt)

    # Check and extend the cache expiration if needed.
    config = repository.get_cache_config()
    if config:
        expires_at_str = config.get(EXPIRES_AT_FIELD)
        if expires_at_str:
            expires_at = datetime.datetime.fromisoformat(expires_at_str)
            current_time = datetime.datetime.now(timezone.utc)
            time_left = expires_at - current_time
            print(f"[DEBUG] Time left on cache: {time_left.total_seconds()} seconds.")
            if time_left.total_seconds() <= CACHE_EXTENSION_THRESHOLD:  # within 5 minutes
                new_expires_at = expires_at + timedelta(seconds=CACHE_EXTENSION_DURATION)
                print(f"[DEBUG] Extending cache expiration by 10 minutes to {new_expires_at.isoformat()}.")
                cache_service.extend_cache_expiration(new_expires_at=new_expires_at, cache_ref=config.get(ACTIVE_CACHE_FIELD))
                print("[DEBUG] Cache extended")
    else:
        print("[DEBUG] No cache config available.")

    active_cache_ref = cache_service.get_active_cache()
    print("Active cache reference obtained:", active_cache_ref)
    if not active_cache_ref:
        print("Cache is not initialized. Cannot process chat request.")
        return jsonify({"error": "Cache not initialized. Please update inventory first."}), 500

    gemini_instance = gemini_integration.instantiate_model_from_cache(active_cache_ref)
    print("Gemini model instantiated using cache:", active_cache_ref)

    # Implement exponential backoff for calling the Gemini API
    attempt = 0
    delay = INITIAL_DELAY
    while attempt < MAX_RETRIES:
        try:
            response = gemini_instance.generate_content(contents=user_prompt)
            # If successful, break out of the retry loop.
            break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                attempt += 1
                print(f"429 error encountered on attempt {attempt}. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                print("An error occurred:", error_str)
                return jsonify({"error": "An internal error occurred."}), 500
    else:
        print("Maximum retry attempts reached.")
        return jsonify({"error": "Too many requests. Please try again later."}), 429

    print("Gemini response usage_metadata:", response.usage_metadata)
    return jsonify({"response": response.text}), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", "8080"))
    print(f"Starting API server on port {port}")
    # For local testing; in production, use a WSGI server like Gunicorn.
    app.run(host='0.0.0.0', port=port, debug=False)
