"""Test TTS only - no LLM"""
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import logging

load_dotenv(Path(__file__).parent.parent / ".env")

from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli
from livekit.agents.voice import AgentSession
from livekit.plugins import elevenlabs

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test-tts")


async def entrypoint(ctx: JobContext):
    logger.info("Connecting...")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    p = await ctx.wait_for_participant()
    logger.info(f"Participant: {p.identity}")

    tts = elevenlabs.TTS(
        voice_id=os.getenv("ELEVENLABS_VOICE_ID", "xvbIPX7VE9oYkosnkbGT"),
        model="eleven_turbo_v2_5",
    )
    
    logger.info("Testing TTS directly...")
    
    # Test TTS synthesis
    async for chunk in tts.synthesize("Hello, testing one two three"):
        logger.info(f"Got TTS chunk: {len(chunk.frame.data)} bytes")
    
    logger.info("TTS test complete")
    await asyncio.sleep(5)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
