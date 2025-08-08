#!/usr/bin/env python3
"""
Utility script to post a welcome message in the #beat-loops channel.
Run this once to encourage new artists to share beats, loops, videos or MP3s.
Requires DISCORD_BOT_TOKEN in the environment.
"""
import os
import asyncio
import discord

# Channel ID for #beat-loops
CHANNEL_ID = 1393809294079819917

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    print("❌ Please set DISCORD_BOT_TOKEN in your environment.")
    exit(1)

intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def send_welcome():
    await client.login(TOKEN)
    channel = await client.fetch_channel(CHANNEL_ID)
    await channel.send(
        "🎶 **Welcome to #beat-loops!** 🎶\n\n"
        "New artists, drop your latest beats, loops, videos or MP3s here — "
        "we can’t wait to hear your creations! 🚀"
    )
    await client.close()

if __name__ == "__main__":
    asyncio.run(send_welcome())
