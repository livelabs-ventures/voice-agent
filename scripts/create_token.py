#!/usr/bin/env python3
"""
Generate a LiveKit access token for testing the voice agent.

Usage:
    python scripts/create_token.py [room_name] [participant_name]
    
Example:
    python scripts/create_token.py badgeroo-room armand
"""

import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

try:
    from livekit.api import AccessToken, VideoGrants
except ImportError:
    print("Install livekit-api: pip install livekit-api")
    sys.exit(1)


def create_token(room_name: str, participant_name: str) -> str:
    """Generate an access token for joining a LiveKit room."""
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    
    if not api_key or not api_secret:
        raise ValueError("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set")
    
    token = AccessToken(api_key, api_secret)
    token.identity = participant_name
    token.name = participant_name
    token.ttl = timedelta(hours=24)
    
    # Grant permissions
    token.video_grants = VideoGrants(
        room=room_name,
        room_join=True,
        room_create=True,  # Allow creating room if it doesn't exist
        can_publish=True,
        can_subscribe=True,
        can_publish_data=True,
    )
    
    return token.to_jwt()


if __name__ == "__main__":
    room = sys.argv[1] if len(sys.argv) > 1 else "badgeroo-voice"
    participant = sys.argv[2] if len(sys.argv) > 2 else "user"
    
    try:
        jwt = create_token(room, participant)
        livekit_url = os.getenv("LIVEKIT_URL", "wss://your-server.livekit.cloud")
        
        print(f"\n🎙️  LiveKit Voice Agent - Test Token")
        print(f"{'=' * 50}")
        print(f"Room:        {room}")
        print(f"Participant: {participant}")
        print(f"Server:      {livekit_url}")
        print(f"\nToken:\n{jwt}")
        print(f"\n🔗 Join URL:")
        print(f"https://meet.livekit.io/custom?liveKitUrl={livekit_url}&token={jwt}")
        print()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
