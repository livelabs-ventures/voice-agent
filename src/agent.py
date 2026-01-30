"""LiveKit Voice Agent - Fast Voice + Async Deep Thinking
gpt-4o-mini direct for instant responses
Opus via Gateway for deep thinking (async, keeps conversation going)
"""
import os
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv
import logging

load_dotenv(Path(__file__).parent.parent / ".env")

from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli, llm
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, elevenlabs, silero, openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

GATEWAY_URL = os.getenv("CLAWDBOT_GATEWAY_URL", "http://127.0.0.1:18789")
GATEWAY_TOKEN = os.getenv("CLAWDBOT_GATEWAY_TOKEN", "")

# Store session reference for async callbacks
_current_session: AgentSession = None


async def _do_deep_think(question: str):
    """Background task for deep thinking - announces result when ready"""
    global _current_session
    logger.info(f"🧠 Deep thinking started: {question}")
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{GATEWAY_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GATEWAY_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "clawdbot:main",  # Route to Opus
                    "messages": [{"role": "user", "content": question}],
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info(f"🧠 Got answer: {answer[:100]}...")
                
                # Use fast model to make it conversational for voice
                voice_response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{
                            "role": "user",
                            "content": f"""Summarize this for a quick voice response (2-3 sentences max, casual and conversational, no bullet points or lists):

{answer[:1500]}"""
                        }],
                    }
                )
                
                if voice_response.status_code == 200:
                    voice_data = voice_response.json()
                    summary = voice_data.get("choices", [{}])[0].get("message", {}).get("content", answer[:200])
                else:
                    # Fallback to simple truncation
                    summary = ". ".join(answer.split(". ")[:2])
                
                if _current_session:
                    await _current_session.say(f"Alright, here's what I found. {summary}")
            else:
                logger.error(f"Deep think failed: {response.status_code}")
                if _current_session:
                    await _current_session.say("Sorry, I couldn't get that info right now.")
    except Exception as e:
        logger.error(f"Deep think error: {e}")
        if _current_session:
            await _current_session.say("Had trouble with that deep thinking request.")


@llm.function_tool
async def deep_think(question: str) -> str:
    """Route complex questions to Opus for deep analysis. Returns immediately - result announced async.
    Use for: code tasks, research, file ops, memory lookups, complex analysis.
    """
    # Fire and forget - don't block voice
    asyncio.create_task(_do_deep_think(question))
    return "I'm thinking about that now. What else can I help with while I work on it?"


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    global _current_session
    
    logger.info(f"Room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant: {participant.identity}")

    agent = Agent(
        instructions="""You are Badgeroo, a super fast rad badger voice assistant.
You work with Armand at LiveLabs Ventures on StreamBridge and Chumo.

VOICE RULES:
- Keep responses SHORT - 1-2 sentences max
- Be snappy and conversational!
- You're fast - respond immediately

DEEP THINKING (use deep_think tool):
- Code tasks, debugging, technical details
- Research, analysis, memory lookups  
- Past work context, file operations
- Complex multi-step tasks

When you call deep_think:
- Say something like "Let me look into that..." or "Good question, checking..."
- The tool returns immediately so you can KEEP TALKING
- The answer will be announced when ready
- Ask "what else?" to keep conversation flowing

You're tenacious and never give up! 🦡""",
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-5.2-chat-latest"),  # ChatGPT voice model!
        tts=elevenlabs.TTS(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "xvbIPX7VE9oYkosnkbGT"),
            model="eleven_turbo_v2_5",
        ),
        tools=[deep_think],
    )

    session = AgentSession()
    _current_session = session  # Store for async callbacks
    
    await session.start(agent, room=ctx.room)
    logger.info("Ready! Fast voice + async deep thinking")
    
    await session.say("Hey Armand! I'm fast for quick stuff, and I'll think deeper in the background for complex questions.")
    
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
