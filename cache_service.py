import datetime
from datetime import timezone, timedelta
from config import ACTIVE_CACHE_FIELD, EXPIRES_AT_FIELD
import repository
import gemini_integration
from vertexai.generative_models import Part

def create_new_cache(inventory_data):
    """
    Create a new Gemini cache using updated inventory data.
    Retrieves the system prompt template from Firestore and creates a new cache.
    """
    system_instruction = repository.get_system_prompt()
    if system_instruction is None:
        # Fallback prompt if not found in Firestore
        system_instruction = (
            "You are a customer support chatbot. Use the following inventory information to answer questions:\n"
            "${inventory_data}"
        )

    # Build the contents as a Content object.
    system_part = Part.from_text(text=system_instruction)
    content_part = Part.from_text(text=inventory_data)
    
    print("[DEBUG] Creating cache...")
    new_cache_ref = gemini_integration.create_cache(
        system_instruction=system_part,
        contents=content_part,
    )
    print("[DEBUG] Cache created.")

    return new_cache_ref

def update_active_cache():
    """
    Update the active cache by creating a new cache and saving the current one as previous.
    """
    inventory_data = repository.get_inventory_data()
    new_cache_ref = create_new_cache(inventory_data)
    current_config = repository.get_cache_config()
    repository.update_cache_config(
        active_cache=new_cache_ref,
    )
    return new_cache_ref

def get_active_cache():
    """
    Determine which cache to use based on the transition period and expiration.
    If the active cache has expired, update the active cache first.
    """
    config = repository.get_cache_config()
    if not config:
        return None

    active_cache = config.get(ACTIVE_CACHE_FIELD)
    expires_at_str = config.get(EXPIRES_AT_FIELD)
    current_time = datetime.datetime.now(timezone.utc)

    # If there's an expiration time and it has passed, update the active cache.
    if expires_at_str:
        expires_at = datetime.datetime.fromisoformat(expires_at_str)
        if current_time >= expires_at:
            # Cache expired, update and return new active cache.
            print("[DEBUG] Cache expired...updating...")
            return update_active_cache()

    return active_cache

def extend_cache_expiration(new_expires_at, cache_ref):
    gemini_integration.extend_cache_expiration(cache_ref=cache_ref)
    repository.extend_cache_expiration(new_expires_at=new_expires_at)


# every time send message, updates expires_at and remove previous_cache if it's expired_at already passed

# ask chat if every should be in one db or each client should have their own seperate db

# add to system prompt to check if inventory is gone

# actually extend the cache expiration of the gemini