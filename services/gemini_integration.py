import datetime
from datetime import timezone
from typing import Optional
import requests
import json

# Import the new SDK
from google import genai
from google.genai import types # Import types for config objects
from google.api_core import exceptions as google_exceptions

from config.config import (
    # GEMINI_MODEL_NAME will be passed to functions needing it
    GOOGLE_API_KEY,
    LOG_LEVEL,
    CALL_A_FRIEND_WEBHOOK_URL
)
from config.logger_config import setup_logger

logger = setup_logger(__name__, level=LOG_LEVEL)

# --- Define custom exceptions ---
class GenAIConfigurationError(Exception):
    """Error configuring the GenAI client or API Key."""
    pass

class CacheCreationError(Exception):
    """Error during GenAI cache creation."""
    pass

class CacheInteractionError(Exception):
    """Error interacting (get, update, delete) with an existing GenAI cache."""
    pass

class GenAIGenerationError(Exception):
    """Error during content generation using the GenAI API."""
    pass


# --- Fetch API Key and Configure SDK Client at module load ---
try:
    
    if not GOOGLE_API_KEY:
        raise GenAIConfigurationError("Fetched Google AI API Key is empty.")

    # Create the client instance using the new SDK pattern
    # The client implicitly uses the API Key from env var if not passed,
    # but explicit passing is clearer.
    client = genai.Client(api_key=GOOGLE_API_KEY)
    logger.info("Google GenAI Client configured successfully.")

    # Optional: Verify client connection by listing models or similar
    # client.models.list()

except (google_exceptions.GoogleAPIError, ValueError, Exception) as e:
    logger.critical(f"CRITICAL: Failed to configure Google GenAI Client: {e}", exc_info=True)
    raise GenAIConfigurationError("Failed to configure Google GenAI Client.") from e

# --- Function Declaration for Calling a Friend ---
REQUEST_COLLEAGUE_HELP_DECLARATION = types.FunctionDeclaration(
    name="request_colleague_help",
    description=(
        "Use this function ONLY when you receive a query you cannot answer based on your "
        "knowledge, the provided inventory data, or defined capabilities (like finance, "
        "test drives, opening hours). This function sends the difficult query and relevant "
        "conversation context to a human colleague for assistance."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            'message_to_colleague': types.Schema(
                type=types.Type.STRING,
                description="A message for the colleague clearly stating the user's original unanswered query and any necessary preceding context from the conversation."
            )
        },
        required=['message_to_colleague']
    )
)

# --- Helper Function to Execute the Webhook Call ---
def _execute_request_colleague_help(message_to_colleague: str) -> dict:
    """
    Sends the message to the colleague via the configured webhook.

    Args:
        message_to_colleague: The message constructed by the model.

    Returns:
        A dictionary indicating success or failure.
    """
    logger.info(f"Executing 'request_colleague_help' function call. Sending message to webhook: {CALL_A_FRIEND_WEBHOOK_URL}")
    payload = {"message": message_to_colleague}
    headers = {'Content-Type': 'application/json'}
    api_response = {"status": "error", "message": "Webhook call failed."} # Default failure response

    try:
        response = requests.post(CALL_A_FRIEND_WEBHOOK_URL, headers=headers, json=payload, timeout=15) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        # Check if the response body matches the expected success message
        response_text = response.text.strip() # Use .text and strip whitespace
        if response_text == '"College successfully contacted"': # Check exact string including quotes if n8n sends it like that
             logger.info("Webhook call successful: Colleague contacted.")
             api_response = {"status": "success", "confirmation": "Colleague successfully contacted."}
        else:
             # Log unexpected success response content
             logger.warning(f"Webhook call succeeded (HTTP {response.status_code}) but returned unexpected content: {response_text}")
             # Treat as success for the model flow, but log it
             api_response = {"status": "success", "confirmation": f"Colleague contact initiated (Response: {response_text})"}


    except requests.exceptions.RequestException as e:
        logger.error(f"Webhook call failed for 'request_colleague_help': {e}", exc_info=True)
        api_response = {"status": "error", "message": f"Failed to contact colleague due to network/request error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error during 'request_colleague_help' execution: {e}", exc_info=True)
        api_response = {"status": "error", "message": f"An unexpected error occurred: {e}"}

    return api_response

# --- Cache Operations ---

def create_cache(
    model_name: str,
    system_instruction: str, # <-- Keep as string type hint
    inventory_data: str,
    ttl_seconds: int,
    tools: Optional[list[types.Tool]] = None,
    display_name: Optional[str] = None
) -> str:
    """
    Creates a new GenAI context cache including system instructions, data, tools,
    and forces the function calling mode to ANY.
    """
    # ... (input validation, logging setup) ...

    ttl_str = f"{ttl_seconds}s"
    cache_display_name = display_name or f"cache-{model_name.split('/')[-1]}-{int(datetime.datetime.now(timezone.utc).timestamp())}"

    logger.info(f"Creating GenAI cache for model '{model_name}' with TTL {ttl_str}")
    if tools:
        tool_names = [d.name for t in tools for d in t.function_declarations] if tools else []
        logger.info(f"Including tools in cache: {tool_names}")

    try:
        # +++ START: Define ToolConfig for Forced Mode +++
        forced_any_tool_config = None
        if tools: # Only add tool_config if tools are actually provided
            forced_any_tool_config = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="any"
                    # Optional: Restrict to specific function names if needed
                    # allowed_function_names=[REQUEST_COLLEAGUE_HELP_DECLARATION.name]
                )
            )
            logger.info("Applying ToolConfig with forced Mode.ANY during cache creation.")
        else:
            logger.info("No tools provided, ToolConfig will not be applied.")
        # +++ END: Define ToolConfig for Forced Mode +++

        # Construct the config including system instruction, content, tools, AND the forced tool_config
        cache_config = types.CreateCachedContentConfig(
            display_name=cache_display_name,
            system_instruction=system_instruction,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text=inventory_data)]
                )
            ],
            ttl=ttl_str,
            tools=tools,
            tool_config=forced_any_tool_config # <-- ADD the tool_config here
        )

        created_cache = client.caches.create(
            model=model_name,
            config=cache_config
        )

        # ... (logging success, verification logs, token checks) ...
        logger.info(f"GenAI cache created successfully: Name='{created_cache.name}', DisplayName='{created_cache.display_name}'")
        # Add verification log again to see if *this* makes tools appear
        try:
            cache_details = client.caches.get(name=created_cache.name)
            has_tools = hasattr(cache_details, 'tools') and cache_details.tools is not None
            tool_names_in_cache = []
            if has_tools and cache_details.tools:
                 tool_names_in_cache = [d.name for t in cache_details.tools for d in t.function_declarations]
            logger.info(f"Verification (Forced ANY Mode) - Cache '{created_cache.name}' details: HasTools={has_tools}, ToolNames={tool_names_in_cache}")
            cached_sys_instruction = getattr(cache_details, 'system_instruction', 'MISSING')
            logger.info(f"Verification (Forced ANY Mode) - System Instruction in cache: '{str(cached_sys_instruction)[:100]}...'")
        except Exception as verify_err:
            logger.error(f"Failed to verify cache details immediately after creation (forced mode): {verify_err}")


        return created_cache.name

    # ... (exception handling remains the same) ...
    except google_exceptions.InvalidArgument as e:
         # Check for role error specifically if needed
         if "content.role set" in str(e):
              logger.error(f"Cache creation failed: Missing role in contents. Error: {e}", exc_info=True)
              # This specific error shouldn't happen with the fix, but good to log if it recurs
              raise CacheCreationError("Cache creation failed: Role missing in contents.") from e
         elif "tool" in str(e).lower() or "function" in str(e).lower():
              logger.error(f"Failed to create cache due to invalid tool/function definition: {e}", exc_info=True)
              raise CacheCreationError(f"Cache creation failed (Invalid Tool/Function): {e}") from e
         else:
              logger.error(f"Failed to create GenAI cache due to invalid argument: {e}", exc_info=True)
              raise CacheCreationError(f"Cache creation failed (Invalid Argument): {e}") from e
    except Exception as e:
        logger.error(f"Failed to create GenAI cache: {e}", exc_info=True)
        raise CacheCreationError(f"Cache creation failed: {e}") from e
     
def generate_content_with_cache(
    model_name: str,
    cache_name: str,
    user_prompt: str
) -> types.GenerateContentResponse:
    """
    Generates content using a previously created cache. The cache itself contains
    the necessary system instructions and tools. Handles function calling loops.
    """
    logger.debug(f"Generating content using cache '{cache_name}' with model '{model_name}'")

    try:
        gen_config = types.GenerateContentConfig(
            cached_content=cache_name
        )

        logger.debug("Making initial generate_content call referencing the cache.")
        initial_contents = [types.Content(role="user", parts=[types.Part(text=user_prompt)])]

        response = client.models.generate_content(
            model=model_name,
            contents=initial_contents,
            config=gen_config
        )

        # --- Check for Function Call ---
        function_calls = []
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            logger.debug("Checking response parts for function calls...")
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    logger.info(f"Detected function call in part: {part.function_call.name}")
                    function_calls.append(part.function_call)

        if function_calls:
            # Assuming only one function call per turn for now
            function_call = function_calls[0]
            function_name = function_call.name
            logger.info(f"Model responded with function call: {function_name}") # Renamed log slightly

            if function_name == REQUEST_COLLEAGUE_HELP_DECLARATION.name:
                 args = function_call.args
                 message = args.get('message_to_colleague', '')
                 if not message:
                     logger.error("Function call 'request_colleague_help' missing 'message_to_colleague' argument.")
                     raise GenAIGenerationError("Function call was incomplete (missing message).")

                 logger.info(f"Calling _execute_request_colleague_help with message: '{message[:50]}...'") # Log execution start
                 api_response_content = _execute_request_colleague_help(message)
                 logger.info(f"Received API response from webhook execution: {api_response_content}") # Log result

                 logger.debug("Sending function execution result back to the model.")
                 # Ensure the model's function call part is included correctly
                 model_function_call_content = response.candidates[0].content

                 conversation_history = [
                     initial_contents[0], # Original user prompt
                     model_function_call_content, # Model's response PART containing the function call
                     types.Content(       # The result of the function call
                         role="user", # Role is 'user' for function responses
                         parts=[
                             types.Part.from_function_response(
                                 name=function_name,
                                 response=api_response_content
                             )
                         ]
                     )
                 ]
                 logger.debug(f"Conversation history for final call: {conversation_history}") #TODO: Send gemini_integration.py to 2.5 with example logs

                 final_response = client.models.generate_content(
                     model=model_name,
                     contents=conversation_history,
                     config=gen_config # Use same config (only cache ref)
                 )
                 logger.info("Received final response from model after function execution.")
                 # --- START: Robust Validation of final_response ---
                 final_text = None
                 if not final_response.candidates:
                     logger.error("Final response after function call has no candidates.")
                     raise GenAIGenerationError("Model returned no candidates in final response after function call.")

                 first_candidate = final_response.candidates[0]

                 # Check finish reason first (important for safety/blocks)
                 if first_candidate.finish_reason != types.FinishReason.STOP:
                     logger.warning(f"Final response finished abnormally. Reason: {first_candidate.finish_reason}")
                     # Handle specific reasons if needed (e.g., raise for SAFETY)
                     if first_candidate.finish_reason == types.FinishReason.SAFETY:
                          raise GenAIGenerationError(f"Final response flagged for safety reasons. Cache: {cache_name}")
                     # Potentially raise for others like MAX_TOKENS, RECITATION etc.

                 # Now check content structure safely
                 if not first_candidate.content or not first_candidate.content.parts:
                     logger.error("Final response after function call is missing content or parts.")
                     # Check if finish reason was STOP despite empty content (unlikely but possible)
                     if first_candidate.finish_reason == types.FinishReason.STOP:
                         logger.warning("Final response finished with STOP but content/parts are missing.")
                         # Maybe return an empty response indicator or raise? Raise for now.
                         raise GenAIGenerationError("Model returned empty content in final response after function call.")
                     else:
                         # If finish reason was abnormal AND content is missing, the reason is the primary issue.
                         # We might have already raised above, but this is a fallback.
                         raise GenAIGenerationError(f"Model returned invalid final response structure after function call. Finish Reason: {first_candidate.finish_reason}")

                 # Safely access the text part
                 try:
                     final_text = first_candidate.content.parts[0].text
                     logger.info(f"Final response text: '{final_text[:100]}...'")
                 except IndexError:
                     logger.error("Final response content.parts is empty.")
                     raise GenAIGenerationError("Model returned final response with no text part after function call.")
                 except AttributeError:
                     logger.error("Final response content.parts[0] missing 'text' attribute.")
                     raise GenAIGenerationError("Model returned final response with unexpected part structure.")
                 except Exception as e: # Catch any other unexpected access error
                     logger.exception("Unexpected error accessing final response text.")
                     raise GenAIGenerationError(f"Error processing final response content: {e}")

                 # If all checks passed, return the final response
                 return final_response
                 # --- END: Robust Validation of final_response ---

            else:
                logger.warning(f"Received unhandled function call: {function_name}")
                # Return the original response containing the unhandled call
                return response
        else:
            # --- No Function Call Detected ---
             logger.info("No function call detected in the initial response.") # Changed level to INFO
             # ... (validation checks remain the same) ...
             if not response.candidates or not response.candidates[0].content or not response.candidates[0].content.parts:
                 logger.warning(f"Generation using cache '{cache_name}' produced no valid candidates/content.")
                 finish_reason = getattr(response.candidates[0], 'finish_reason', None) if response.candidates else None
                 if finish_reason == types.FinishReason.SAFETY:
                      raise GenAIGenerationError(f"Response flagged for safety reasons using cache '{cache_name}'.")
                 raise GenAIGenerationError(f"Model returned empty/invalid response using cache '{cache_name}'. Finish Reason: {finish_reason}")

             first_candidate = response.candidates[0]
             if first_candidate.finish_reason != types.FinishReason.STOP:
                 logger.warning(f"Generation finished abnormally using cache '{cache_name}'. Reason: {first_candidate.finish_reason}")
                 if first_candidate.finish_reason == types.FinishReason.SAFETY:
                      raise GenAIGenerationError(f"Response flagged for safety reasons. Cache: {cache_name}")

             logger.debug("Content generated successfully using cache (no function call).")
             return response

    # ... (exception handling remains the same) ...
    except google_exceptions.NotFound as e:
         logger.error(f"Cache not found or invalid: {cache_name}. Error: {e}")
         raise CacheInteractionError(f"Cache not found or invalid: {cache_name}") from e
    except google_exceptions.InvalidArgument as e:
         logger.error(f"Invalid argument using cache '{cache_name}': {e}")
         raise CacheInteractionError(f"Invalid argument using cache '{cache_name}': {e}") from e
    except google_exceptions.ResourceExhausted as e:
        logger.warning(f"Rate limit likely hit using cache '{cache_name}': {e}")
        raise # Let caller handle retry
    except GenAIGenerationError: # Re-raise specific errors
        raise
    except Exception as e:
        logger.error(f"Unexpected error during GenAI generation with cache '{cache_name}': {e}", exc_info=True)
        raise GenAIGenerationError(f"Unexpected error during generation with cache '{cache_name}': {e}") from e
     
def extend_cache_expiry(cache_name: str, new_expiry_time: datetime.datetime) -> None:
    """
    Updates the expiration time of an existing GenAI context cache.

    Args:
        cache_name: The resource name (ID) of the cache to update (e.g., "cachedContents/xyz123").
        new_expiry_time: The new absolute expiration time (must be timezone-aware UTC).

    Raises:
        CacheInteractionError: If updating the cache fails (e.g., not found).
        ValueError: If new_expiry_time is not timezone-aware UTC.
    """
    if new_expiry_time.tzinfo is None or new_expiry_time.tzinfo.utcoffset(new_expiry_time) != datetime.timedelta(0):
        raise ValueError("new_expiry_time must be timezone-aware and in UTC.")

    logger.info(f"Attempting to update expiry for cache '{cache_name}' to {new_expiry_time.isoformat()}")

    try:
        # Use types.UpdateCachedContentConfig
        update_config = types.UpdateCachedContentConfig(expire_time=new_expiry_time)
        # Call update using the client
        client.caches.update(name=cache_name, config=update_config)
        logger.info(f"Successfully updated expiry for cache '{cache_name}'")
    except google_exceptions.NotFound as e:
        logger.error(f"Cannot update expiry: Cache not found: {cache_name}. Error: {e}")
        raise CacheInteractionError(f"Cannot update expiry: Cache not found: {cache_name}") from e
    except google_exceptions.InvalidArgument as e:
         logger.error(f"Invalid argument updating expiry for cache '{cache_name}': {e}")
         raise CacheInteractionError(f"Invalid argument updating expiry for cache '{cache_name}': {e}") from e
    except Exception as e:
        logger.error(f"Failed to update expiry for cache '{cache_name}': {e}", exc_info=True)
        raise CacheInteractionError(f"Failed to update expiry for cache '{cache_name}': {e}") from e


def delete_cache(cache_name: str) -> None:
    """
    Deletes a GenAI context cache using the google.genai SDK.

    Args:
        cache_name: The resource name (ID) of the cache to delete (e.g., "cachedContents/xyz123").

    Raises:
        CacheInteractionError: If deleting the cache fails unexpectedly.
    """
    logger.info(f"Attempting to delete cache: {cache_name}")
    try:
        # Call delete using the client
        client.caches.delete(name=cache_name)
        logger.info(f"Successfully deleted cache: {cache_name}")
    except google_exceptions.NotFound as e:
        # Deleting a non-existent cache is often okay, just log it.
        logger.warning(f"Attempted to delete non-existent cache: {cache_name}. Error: {e}")
        # No exception raised here, treat as success (idempotent delete)
    except Exception as e:
        logger.error(f"Failed to delete cache '{cache_name}': {e}", exc_info=True)
        raise CacheInteractionError(f"Failed to delete cache '{cache_name}': {e}") from e