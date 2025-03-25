from vertexai.preview import caching
from vertexai.preview.generative_models import GenerativeModel
from config import GEMINI_MODEL_NAME

def create_cache(system_instruction, ttl, contents=None):
    """
    Create a new Gemini context cache using the given system instruction.
    """
    if contents is None:
        contents = []
    new_cache = caching.CachedContent.create(
        model_name=GEMINI_MODEL_NAME,
        system_instruction=system_instruction,
        contents=contents,
        ttl=ttl
    )
    return new_cache.name

def instantiate_model_from_cache(cache_ref):
    """
    Instantiate a Gemini model from an existing context cache.
    """
    cached_content = caching.CachedContent(cached_content_name=cache_ref)
    return GenerativeModel.from_cached_content(cached_content=cached_content)
