import vertexai
from vertexai.preview import caching
from vertexai.preview.generative_models import GenerativeModel
from config import GEMINI_MODEL_NAME, CACHE_TTL, GCP_PROJECT_ID, VERTEX_AI_REGION, CACHE_EXTENSION_DURATION
from datetime import timedelta
from logger_config import setup_logger

logger = setup_logger(__name__)

# Initialize Vertex AI for the given project and location.
vertexai.init(project=GCP_PROJECT_ID, location=VERTEX_AI_REGION)

def create_cache(system_instruction, contents):
    """
    Create a new Gemini context cache using the given system instruction and inventory data.
    """
    new_cache = caching.CachedContent.create(
        model_name=GEMINI_MODEL_NAME,
        system_instruction=system_instruction,
        contents=contents,
        ttl=timedelta(seconds=int(CACHE_TTL))
    )
    return new_cache.name

def instantiate_model_from_cache(cache_ref):
    """
    Instantiate a Gemini model from an existing context cache.
    """
    cached_content = caching.CachedContent(cached_content_name=cache_ref)
    return GenerativeModel.from_cached_content(cached_content=cached_content)

def extend_cache_expiration(cache_ref):
    """
    Extend cache expiration date.
    """
    cached_content = caching.CachedContent(cached_content_name=cache_ref)
    cached_content.update(ttl=timedelta(seconds=int(CACHE_EXTENSION_DURATION)))
    cached_content.refresh()
    logger.info("Gemini cache expiration extended for cache_ref: %s", cache_ref)
