"""
Clawdbot Gateway LLM Adapter for LiveKit Agents

Routes voice transcriptions through Clawdbot Gateway to maintain
session context, memory, and tool access.
"""

import os
import httpx
from dataclasses import dataclass

from livekit.agents import llm, APIConnectOptions
from livekit.agents.types import NOT_GIVEN, NotGivenOr


@dataclass
class ClawdbotLLMOptions:
    gateway_url: str = "http://127.0.0.1:18789"
    session_key: str = "agent:voice"
    timeout: float = 60.0


class ClawdbotLLM(llm.LLM):
    """
    Custom LLM that routes to Clawdbot Gateway.
    
    Maintains session continuity so the voice agent has access to:
    - Conversation history
    - Memory (MEMORY.md)
    - All configured tools
    - User profile context
    """

    def __init__(self, opts: ClawdbotLLMOptions | None = None):
        super().__init__()
        self._opts = opts or ClawdbotLLMOptions(
            gateway_url=os.getenv("CLAWDBOT_GATEWAY_URL", "http://127.0.0.1:18789"),
            session_key=os.getenv("CLAWDBOT_SESSION_KEY", "agent:voice"),
        )
        self._client = httpx.AsyncClient(timeout=self._opts.timeout)

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = APIConnectOptions(),
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[llm.ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict] = NOT_GIVEN,
    ) -> "ClawdbotLLMStream":
        # Extract the latest user message
        user_message = ""
        for msg in reversed(chat_ctx.items):
            # Role is now a string literal: 'user', 'assistant', 'system', 'developer'
            if msg.role == "user":
                # Get text content from message
                text = msg.text_content
                if text:
                    user_message = text
                    break

        return ClawdbotLLMStream(
            client=self._client,
            opts=self._opts,
            message=user_message,
            chat_ctx=chat_ctx,
            conn_options=conn_options,
        )


class ClawdbotLLMStream(llm.LLMStream):
    """Streams responses from Clawdbot Gateway."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        opts: ClawdbotLLMOptions,
        message: str,
        chat_ctx: llm.ChatContext,
        conn_options: APIConnectOptions,
    ):
        super().__init__(
            chat_ctx=chat_ctx,
            conn_options=conn_options,
        )
        self._client = client
        self._opts = opts
        self._message = message

    async def _run(self) -> None:
        """Execute the request to Clawdbot Gateway."""
        
        try:
            payload = {
                "message": self._message,
                "sessionKey": self._opts.session_key,
            }
            
            # Try the chat endpoint
            response = await self._client.post(
                f"{self._opts.gateway_url}/api/v1/chat",
                json=payload,
                timeout=self._opts.timeout,
            )
            
            if response.status_code == 200:
                data = response.json()
                text = data.get("response", data.get("content", str(data)))
                
                # Emit as a single chunk
                chunk = llm.ChatChunk(
                    id="clawdbot-response",
                    delta=llm.ChoiceDelta(
                        role="assistant",
                        content=text,
                    ),
                )
                self._event_ch.send_nowait(chunk)
            else:
                raise llm.LLMError(f"Gateway returned {response.status_code}")
                
        except httpx.HTTPError as e:
            raise llm.LLMError(f"Clawdbot Gateway error: {e}")
        except Exception as e:
            raise llm.LLMError(f"Failed to connect to Clawdbot Gateway: {e}")
