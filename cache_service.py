import datetime
from datetime import timezone, timedelta
from config import TRANSITION_PERIOD_SECONDS, CACHE_TTL, ACTIVE_CACHE_FIELD, PREVIOUS_CACHE_FIELD, TRANSITION_UNTIL_FIELD
import repository
import gemini_integration

def create_new_cache(inventory_data):
    """
    Create a new Gemini cache using updated inventory data.
    Retrieves the system prompt template from Firestore, replaces the placeholder
    "${inventory_data}" with the provided inventory data, and creates a new cache.
    """
    prompt_template = repository.get_system_prompt()
    if prompt_template is None:
        # Fallback prompt if not found in Firestore
        prompt_template = (
            "You are a customer support chatbot. Use the following inventory information to answer questions:\n"
            "${inventory_data}"
        )
    # Replace the placeholder with actual inventory data
    system_instruction = prompt_template.replace("${inventory_data}", inventory_data)
    
    new_cache_ref = gemini_integration.create_cache(
        system_instruction=system_instruction,
        ttl=CACHE_TTL
    )
    return new_cache_ref

def update_active_cache(new_inventory_data):
    """
    Update the active cache by creating a new cache and saving the current one as previous.
    """
    new_cache_ref = create_new_cache(new_inventory_data)
    current_config = repository.get_cache_config()
    previous_cache = current_config.get(ACTIVE_CACHE_FIELD) if current_config else None
    transition_until = datetime.datetime.now(timezone.utc) + timedelta(seconds=TRANSITION_PERIOD_SECONDS)
    repository.update_cache_config(active_cache=new_cache_ref, previous_cache=previous_cache, transition_until=transition_until)
    return new_cache_ref

def get_active_cache():
    """
    Determine which cache to use based on the transition period.
    """
    config = repository.get_cache_config()
    if not config:
        return None
    active_cache = config.get(ACTIVE_CACHE_FIELD)
    previous_cache = config.get(PREVIOUS_CACHE_FIELD)
    transition_until_str = config.get(TRANSITION_UNTIL_FIELD)
    if transition_until_str:
        transition_until = datetime.datetime.fromisoformat(transition_until_str)
        current_time = datetime.datetime.now(timezone.utc)
        if current_time < transition_until and previous_cache:
            return previous_cache
    return active_cache
