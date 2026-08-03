import platform
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional, Any, Literal
from anthropic import AsyncAnthropic, APIError
from app.agent.tools.collection import ToolCollection
from app.core.config import settings

COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"
PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"

ThinkingMode = Literal["adaptive", "extended", "off"]
ThinkingEffort = Literal["low", "medium", "high", "max"]

SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are controlling an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can feel free to install Ubuntu applications with your bash tool. Use curl instead of wget.
* To open the web browser or perform web searches, launch Firefox via bash tool using "firefox-esr &". Firefox is the default web browser on this system. Multiple sessions run concurrently with isolated browser profiles on the same desktop.
* Using bash tool you can start GUI applications. The DISPLAY environment variable is pre-configured. Do NOT set export DISPLAY, do NOT prefix commands with DISPLAY=, and do NOT use DISPLAY subshells. Run GUI commands directly (e.g. "firefox-esr &" or "xterm &").
* Save downloaded files and images directly to ~/Desktop or /root/Desktop so they are visible on the desktop.
* Take a screenshot after executing GUI actions or completing a segment to analyze the screen state.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.
* The current date is {datetime.today().strftime("%A, %B %d, %Y")}.
</SYSTEM_CAPABILITY>

<SEGMENT_EXECUTION_WORKFLOW>
* Work segment-by-segment:
  1. Observe & Analyze Screenshot: Carefully analyze the current screen screenshot (identify UI elements, buttons, text, inputs, and coordinates).
  2. Plan Action: State clearly what you intend to click, type, or execute.
  3. Execute Action & Capture Screenshot: Perform the action (e.g. mouse_move, left_click, type, key, or bash command) and ensure a screenshot is captured at the end of the segment.
  4. Evaluate Outcome: Examine the resulting screenshot, confirm whether the action succeeded, and determine the next action needed.
</SEGMENT_EXECUTION_WORKFLOW>

<IMPORTANT>
* When using Firefox, if a startup wizard appears, IGNORE IT. Click directly on the address bar where it says "Search or enter address".
* If inspecting a PDF, convert it or download it with curl/pdftotext if extensive reading is needed.
</IMPORTANT>"""

async def sampling_loop(
    messages: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = "claude-3-5-sonnet-latest",
    tools: Optional[ToolCollection] = None,
    display: Optional[str] = None,
    session_id: Optional[str] = None,
    max_tokens: int = 4096,
    max_steps: int = 15,
    thinking_mode: ThinkingMode = "off",
    thinking_effort: ThinkingEffort = "medium",
    thinking_budget: Optional[int] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executes the Anthropic computer use agent sampling loop adapted for FastAPI real-time streaming.
    Yields structured stream events (status, text, tool_use, tool_result, error, finished).
    """
    key = api_key or settings.ANTHROPIC_API_KEY
    if not key:
        yield {"type": "error", "error": "Anthropic API Key is missing. Please set ANTHROPIC_API_KEY in your .env file."}
        return

    client = AsyncAnthropic(api_key=key)
    tool_collection = tools or ToolCollection(display=display, session_id=session_id)
    tool_params = tool_collection.to_params()

    current_messages = list(messages)
    step_count = 0

    # Model fallback queue
    candidate_models = []
    for m in [model, settings.DEFAULT_MODEL, "claude-sonnet-4-6", "claude-sonnet-5", "claude-sonnet-4-5-20250929", "claude-opus-4-6", "claude-3-5-sonnet-20241022", "claude-3-5-sonnet-latest", "claude-3-7-sonnet-20250219", "claude-3-opus-20240229"]:
        if m and m not in candidate_models:
            candidate_models.append(m)


    selected_model = candidate_models[0]

    # Extra body configuration for thinking mode
    extra_body = {}
    if thinking_mode == "adaptive":
        extra_body = {
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": thinking_effort},
        }
    elif thinking_mode == "extended" and thinking_budget:
        extra_body = {
            "thinking": {"type": "enabled", "budget_tokens": thinking_budget}
        }

    while step_count < max_steps:
        step_count += 1
        yield {"type": "status", "status": f"Step {step_count}/{max_steps}: Querying Claude ({selected_model})..."}

        response = None
        last_exception = None

        for m_try in candidate_models:
            try:
                betas = []
                if "20241022" in m_try:
                    betas.append(COMPUTER_USE_BETA_FLAG)

                kwargs = {
                    "model": m_try,
                    "max_tokens": max_tokens,
                    "messages": current_messages,
                    "system": SYSTEM_PROMPT,
                    "tools": tool_params,
                }
                if extra_body:
                    kwargs["extra_body"] = extra_body

                if betas:
                    response = await client.beta.messages.create(betas=betas, **kwargs)
                else:
                    response = await client.messages.create(**kwargs)

                selected_model = m_try
                break


            except APIError as e:
                last_exception = e
                if e.status_code == 404 or "not_found_error" in str(e):
                    continue
                else:
                    yield {"type": "error", "error": f"Anthropic API Error: {str(e)}"}
                    return
            except Exception as e:
                yield {"type": "error", "error": f"Unexpected Error: {str(e)}"}
                return

        if response is None:
            err_msg = (
                f"Anthropic API Error (404 Not Found): The provided ANTHROPIC_API_KEY in .env "
                f"does not have access to Claude models or has expired/invalid permissions. "
                f"Please update ANTHROPIC_API_KEY in your .env file with a valid key from https://console.anthropic.com."
            )
            yield {"type": "error", "error": err_msg}
            return

        # Process response content blocks
        assistant_content = []
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
                yield {"type": "text", "text": block.text}
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
                tool_uses.append(block)
                yield {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                }

        # Record assistant response in chat thread
        current_messages.append({"role": "assistant", "content": assistant_content})

        # If no tool calls, loop completed
        if not tool_uses or response.stop_reason == "end_turn":
            yield {"type": "status", "status": "Task completed."}
            break

        # Process tool execution calls
        tool_results_content = []
        for tool_use in tool_uses:
            yield {
                "type": "status", 
                "status": f"Executing tool '{tool_use.name}'..."
            }
            
            result = await tool_collection.run(tool_use.name, tool_use.input)
            
            yield {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "name": tool_use.name,
                "output": result.output,
                "error": result.error,
                "base64_image": result.base64_image
            }

            tool_results_content.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result.to_content_blocks(),
                "is_error": bool(result.error)
            })

        # Add tool results back to chat thread for next loop iteration
        current_messages.append({"role": "user", "content": tool_results_content})

    yield {"type": "finished", "messages": current_messages}
