"""LiveKit Voice Agent - gpt-5.2-chat-latest with context + deep_think for tools"""
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

_session: AgentSession = None
_busy = False

# Context for the voice agent
CONTEXT = """You are Badgeroo 🦡, Armand's voice assistant.

ABOUT ARMAND:
- Founder of LiveLabs Ventures (Cape Town)
- Working on StreamBridge (multi-camera live streaming) and Chumo (streaming for institutes)
- Ultra runner (Hardrock 100, UTCT 100km)
- Previously: Hornet Networks CTO (scaled to 30M users), Pulse founder

CURRENT PROJECTS:
- Voice agent development (this project!)
- Clawdbot integration
- LiveKit for real-time voice

STYLE:
- Keep responses to 1 sentence max
- Be casual and conversational
- You're fast and snappy!

For complex tasks (code, files, research, memory lookups), use deep_think ONCE."""


async def _think(q: str):
    global _session, _busy
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(f"{GATEWAY_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {GATEWAY_TOKEN}", "Content-Type": "application/json"},
                json={"model": "clawdbot:main", "messages": [{"role": "user", "content": q}]})
            if r.status_code == 200:
                ans = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                # Keep it short for voice
                short = ans[:300] + "..." if len(ans) > 300 else ans
                if _session:
                    await _session.say(short)
            else:
                logger.error(f"Gateway returned {r.status_code}")
    except Exception as e:
        logger.error(f"Think error: {e}")
    finally:
        _busy = False


@llm.function_tool
async def deep_think(question: str) -> str:
    """Route to Opus (via Clawdbot) for complex tasks: code, files, research, memory, past work.
    This gives access to tools and context. Call ONCE per topic.
    """
    global _busy
    if _busy:
        return "Still working on the last one, hang on."
    _busy = True
    asyncio.create_task(_think(question))
    return "On it, checking with my deep brain."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    global _session
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    p = await ctx.wait_for_participant()
    logger.info(f"Participant: {p.identity}")

    agent = Agent(
        instructions=CONTEXT,
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-5.2-chat-latest"),
        tts=elevenlabs.TTS(voice_id=os.getenv("ELEVENLABS_VOICE_ID", "xvbIPX7VE9oYkosnkbGT"), model="eleven_turbo_v2_5"),
        tools=[deep_think],
    )

    _session = AgentSession()
    await _session.start(agent, room=ctx.room)
    await _session.say("Hey Armand!")
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
