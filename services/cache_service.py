import datetime
from datetime import timezone, timedelta
from config.config import ACTIVE_CACHE_FIELD, EXPIRES_AT_FIELD
import services.repository as repository
import services.gemini_integration as gemini_integration
from vertexai.generative_models import Part
from config.logger_config import setup_logger

logger = setup_logger(__name__)

def create_new_cache(inventory_data):
    """
    Create a new Gemini cache using updated inventory data.
    """
    system_instruction = repository.get_system_prompt()
    if system_instruction is None:
        system_instruction = (
            "You are a customer support chatbot. Use the following inventory information to answer questions:\n"
            "${inventory_data}"
        )

    system_part = Part.from_text(text=system_instruction)
    content_part = Part.from_text(text=inventory_data)
    
    logger.info("Creating new cache.")
    new_cache_ref = gemini_integration.create_cache(
        system_instruction=system_part,
        contents=content_part,
    )
    logger.info("New cache created: %s", new_cache_ref)
    return new_cache_ref

def update_active_cache():
    """
    Update the active cache by creating a new cache and updating configuration.
    """
    inventory_data = repository.get_inventory_data()
    new_cache_ref = create_new_cache(inventory_data)
    repository.update_cache_config(active_cache=new_cache_ref)
    return new_cache_ref

def get_active_cache():
    """
    Return the active cache, updating it if expired.
    """
    config = repository.get_cache_config()
    if not config:
        return None

    active_cache = config.get(ACTIVE_CACHE_FIELD)
    expires_at_str = config.get(EXPIRES_AT_FIELD)
    current_time = datetime.datetime.now(timezone.utc)

    if expires_at_str:
        expires_at = datetime.datetime.fromisoformat(expires_at_str)
        if current_time >= expires_at:
            logger.info("Cache expired. Updating active cache.")
            return update_active_cache()

    return active_cache

def extend_cache_expiration(new_expires_at, cache_ref):
    gemini_integration.extend_cache_expiration(cache_ref=cache_ref)
    repository.extend_cache_expiration(new_expires_at=new_expires_at)


# every time send message, updates expires_at and remove previous_cache if it's expired_at already passed

# ask chat if every should be in one db or each client should have their own seperate db

# add to system prompt to check if inventory is gone

# actually extend the cache expiration of the gemini