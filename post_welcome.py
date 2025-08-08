#!/usr/bin/env python3
"""
Utility script to post a welcome message in the #beat-loops channel.
Run this once to encourage new artists to share beats, loops, videos or MP3s.
Requires DISCORD_BOT_TOKEN in the environment.
"""

import os
import asyncio
import aiohttp

# Channel ID for #beat-loops
CHANNEL_ID = 1393809294079819917

from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ Please set DISCORD_BOT_TOKEN in your environment or .env file.")
    exit(1)

WELCOME_TEXT = (
    "🎶 **Welcome to #beat-loops!** 🎶\n\n"
    "New artists, drop your latest beats, loops, videos or MP3s here — "
    "we can’t wait to hear your creations! 🚀"
)

async def send_welcome():
    url = f"https://discord.com/api/channels/{CHANNEL_ID}/messages"
    headers = {
        "Authorization": f"Bot {TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"content": WELCOME_TEXT}
    async with aiohttp.ClientSession() as session:
        resp = await session.post(url, headers=headers, json=payload)
        if resp.status not in (200, 201):
            text = await resp.text()
            print(f"❌ Failed ({resp.status}): {text}")

if __name__ == "__main__":
    asyncio.run(send_welcome())
