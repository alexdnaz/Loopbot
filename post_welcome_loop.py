#!/usr/bin/env python3
"""
Utility script to post a welcome message in the #welcome channel.
Requires DISCORD_BOT_TOKEN in the environment or a .env file.
"""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ Please set DISCORD_BOT_TOKEN in your environment or .env file.")
    exit(1)

# Channel ID for #welcome
CHANNEL_ID = 1393807671525773322

WELCOME_TEXT = (
    "👋 **Welcome to The Loop!** 👋\n\n"
    "Dive into the community at https://dailyloop.xyz — "
    "join daily creative challenges, share your loops & beats, and connect with fellow creators!"
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
