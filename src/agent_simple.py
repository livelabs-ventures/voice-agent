"""Minimal voice agent - no tools, just voice"""
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import logging

load_dotenv(Path(__file__).parent.parent / ".env")

from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, elevenlabs, silero, openai

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("voice-agent")


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    logger.info(f"Room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    p = await ctx.wait_for_participant()
    logger.info(f"Participant: {p.identity}")

    agent = Agent(
        instructions="You are a helpful assistant. Keep responses brief.",
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-4o"),  # Known working model
        tts=elevenlabs.TTS(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "xvbIPX7VE9oYkosnkbGT"),
            model="eleven_turbo_v2_5",
        ),
    )

    session = AgentSession()
    await session.start(agent, room=ctx.room)
    logger.info("Session started")
    
    await session.say("Hey!")
    logger.info("Greeting sent")
    
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
