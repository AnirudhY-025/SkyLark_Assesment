"""OpenRouter LLM client with tool-calling agent loop."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from openai import OpenAI

from agent.monday_client import MondayClient
from agent.prompts import SYSTEM_PROMPT
from agent.tools import TOOL_SCHEMAS, execute_tool


DEFAULT_MODEL = "openai/gpt-4o-mini"
MAX_TOOL_CALLS = 8


class LLMClient:
    """Wraps OpenRouter (OpenAI-compatible) with tool-calling loop."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        monday_client: MondayClient,
        tools_enabled: bool = True,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Run the agent loop: send messages → handle tool calls → return final text & tool traces.

        Returns (final_assistant_text, executed_tools).
        """
        # Ensure system prompt is present
        if not messages or messages[0].get("role") != "system":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        executed_tools: list[dict[str, Any]] = []

        for _ in range(MAX_TOOL_CALLS):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_SCHEMAS if tools_enabled else None,
                    tool_choice="auto" if tools_enabled else None,
                    max_tokens=4096,
                )
            except Exception as e:
                # Retry once
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        tools=TOOL_SCHEMAS if tools_enabled else None,
                        tool_choice="auto" if tools_enabled else None,
                        max_tokens=4096,
                    )
                except Exception:
                    return f"I'm sorry, I'm having trouble connecting to the AI service right now. Please try again in a moment. (Error: {str(e)[:200]})", executed_tools

            choice = response.choices[0]
            message = choice.message

            # If no tool calls, return the text response
            if not message.tool_calls:
                return message.content or "", executed_tools

            # Process tool calls
            # Add assistant message with tool calls to history
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })

            # Execute each tool call
            for tc in message.tool_calls:
                import json
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                result = execute_tool(monday_client, tc.function.name, args)
                executed_tools.append({
                    "name": tc.function.name,
                    "arguments": args,
                    "result_snippet": result[:600] + "..." if len(result) > 600 else result,
                })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # If we hit max tool calls, summarize what we have
        return "I've gathered the available data but reached the analysis limit for this turn. Here's what I found so far — feel free to ask a more specific follow-up question.", executed_tools

