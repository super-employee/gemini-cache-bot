import os
from flask import Flask, request, jsonify
import cache_service
import gemini_integration
import firebase_init

app = Flask(__name__)

@app.route('/update_inventory', methods=['POST'])
def update_inventory():
    """
    HTTP endpoint to update inventory.
    """
    data = request.get_json()
    new_inventory = data.get("inventory")
    if not new_inventory:
        return jsonify({"error": "No inventory data provided"}), 400
    new_cache_ref = cache_service.update_active_cache(new_inventory)
    return jsonify({"new_cache": new_cache_ref}), 200

@app.route('/chat', methods=['POST'])
def chat():
    """
    Chat endpoint that processes user queries using the current active cache.
    """
    data = request.get_json()
    user_prompt = data.get("prompt")
    if not user_prompt:
        return jsonify({"error": "No prompt provided."}), 400

    active_cache_ref = cache_service.get_active_cache()
    if not active_cache_ref:
        return jsonify({"error": "Cache not initialized. Please update inventory first."}), 500

    gemini_instance = gemini_integration.instantiate_model_from_cache(active_cache_ref)
    # Call the actual Gemini API to process the prompt.
    response = gemini_instance.process_prompt(user_prompt)  # Replace with the real method.
    return jsonify({"response": response}), 200

if __name__ == '__main__':
    # For local testing; in production, use a WSGI server like Gunicorn.
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", "8080")), debug=False)
