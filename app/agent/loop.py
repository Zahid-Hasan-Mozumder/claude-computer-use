import asyncio
from typing import AsyncGenerator, Callable, Dict, List, Optional, Any
from anthropic import AsyncAnthropic, APIError
from app.agent.tools.collection import ToolCollection
from app.core.config import settings

COMPUTER_USE_BETA_FLAG = "computer-use-2024-10-22"

async def sampling_loop(
    messages: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    model: str = "claude-3-5-sonnet-20241022",
    tools: Optional[ToolCollection] = None,
    max_tokens: int = 4096,
    max_steps: int = 15,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Executes the Anthropic computer use agent sampling loop.
    Yields structured stream events (text, tool_use, tool_result, screenshot, error, finished).
    """
    key = api_key or settings.ANTHROPIC_API_KEY
    if not key:
        yield {"type": "error", "error": "Anthropic API Key is missing. Please set ANTHROPIC_API_KEY env var."}
        return

    client = AsyncAnthropic(api_key=key)
    tool_collection = tools or ToolCollection()
    tool_params = tool_collection.to_params()

    system_prompt = (
        "You are an AI computer use assistant. You can control a desktop environment using "
        "the computer tool, run terminal commands via bash, and view/edit files with str_replace_editor. "
        "Complete user tasks step-by-step accurately."
    )

    current_messages = list(messages)
    step_count = 0

    while step_count < max_steps:
        step_count += 1
        yield {"type": "status", "status": f"Step {step_count}/{max_steps}: Querying Claude..."}

        try:
            response = await client.beta.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=current_messages,
                system=system_prompt,
                tools=tool_params,
                betas=[COMPUTER_USE_BETA_FLAG],
            )
        except APIError as e:
            yield {"type": "error", "error": f"Anthropic API Error: {str(e)}"}
            return
        except Exception as e:
            yield {"type": "error", "error": f"Unexpected Error: {str(e)}"}
            return

        # Process response blocks
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
