import os
import discord
import asyncio
import sqlite3
import itertools
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime

import openai
import sys

# Load environment variables
# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')
# Determine if we're running in single-run mode (cron) vs. normal loop
_RUN_MODE = sys.argv[1] if len(sys.argv) > 1 else None
# Enable or disable the built-in daily scheduling (set RUN_SCHEDULE=false to rely on external cron)
_RUN_SCHEDULE = os.getenv('RUN_SCHEDULE', 'true').lower() not in ('false', '0', 'no')

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot initialization
bot = commands.Bot(command_prefix='!', intents=intents)

# Channel IDs (replace these with your actual channel IDs)
CHALLENGE_CHANNEL_ID = 1393808509463691294  # #current-challenge
SUBMISSIONS_CHANNEL_ID = 1393808617354035321 # #submissions
LEADERBOARD_CHANNEL_ID = 1393810922396585984 # #leaderboard

# SQLite DB setup
conn = sqlite3.connect('rankings.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS rankings (
    user_id TEXT PRIMARY KEY,
    points INTEGER
)''')
conn.commit()

# Static fallback prompts
static_prompts = itertools.cycle([
    "🌿 Create a loop inspired by nature's rhythm.",
    "💭 Make something based on a dream you had.",
    "🚀 Design a sound/scene/story from the future.",
    "🌀 Loop based on the feeling of déjà vu.",
    "🔥 Create something chaotic, messy, raw."
])

# Generate a prompt using GPT
async def generate_ai_prompt():
    try:
        response = openai.ChatCompletion.acreate(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a creative challenge bot that generates short, unique prompts for music, art, or storytelling."},
                {"role": "user", "content": "Give me a short, vivid creative challenge prompt for a Discord community."}
            ],
                max_tokens=100,
            temperature=0.85
        )
        data = await response
        return data.choices[0].message.content.strip()
    except Exception as e:
        print(f"[❌] OpenAI error: {e}")
        return next(static_prompts)

# Unified prompt fetcher
async def get_prompt():
    return await generate_ai_prompt()

# On bot startup
@bot.event
async def on_ready():
    print(f"🤑 Logged in as: {bot.user}")
    # If invoked in single-run mode via cron, perform that action once and exit
    if _RUN_MODE == 'daily':
        channel = bot.get_channel(CHALLENGE_CHANNEL_ID)
        if channel:
            prompt = await get_prompt()
            await channel.send(f"🎯 **Daily Challenge**:\n{prompt}")
        await bot.close()
        return

    if _RUN_MODE == 'leaderboard':
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if channel:
            c.execute(
                "SELECT user_id, points FROM rankings ORDER BY points DESC LIMIT 5"
            )
            top = c.fetchall()
            text = "🏆 **Top 5 Creators:**\n" + "\n".join(
                [f"{i+1}. <@{user}> – {pts} pts" for i, (user, pts) in enumerate(top)]
            )
            await channel.send(text)
        await bot.close()
        return

    # Normal operation: start the daily challenge loop if scheduling is enabled
    if _RUN_SCHEDULE:
        try:
            post_daily_challenge.start()
        except RuntimeError:
            pass
    else:
        print(
            "🕒 Automatic scheduling disabled (RUN_SCHEDULE=false); skipping daily loop startup."
        )

# Daily challenge poster
@tasks.loop(hours=24)
async def post_daily_challenge():
    channel = bot.get_channel(CHALLENGE_CHANNEL_ID)
    if channel:
        prompt = await get_prompt()
        await channel.send(f"🎯 **Daily Challenge**:\n{prompt}")
    else:
        print("⚠️ Challenge channel not found. Check CHALLENGE_CHANNEL_ID.")

# Commands
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

@bot.command(name='commands')
async def list_commands(ctx):
    await ctx.send("📜 Commands: `!ping`, `!submit <link>`, `!rank`, `!leaderboard`, `!postprompt`")

@bot.command(name='how')
async def how(ctx):
    """Explain how to participate in the daily creative challenge."""
    how_text = (
        "👋 **How to use LoopBot:**\n"
        "1. Each morning, check the daily challenge in the designated channel or with `!postprompt`.\n"
        "2. Create your work and submit it with `!submit <link>`.\n"
        "3. Earn 1 point per submission and bonus points for 👍 reactions.\n"
        "4. View your score with `!rank` and the top creators with `!leaderboard`.\n"
        "5. Administrators can manually post a prompt using `!postprompt`.\n"
        "6. Use `!ping` to check if I'm alive!"
    )
    await ctx.send(how_text)

@bot.command()
async def submit(ctx, link: str):
    user_id = str(ctx.author.id)
    c.execute("INSERT OR REPLACE INTO rankings (user_id, points) VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + 1)", (user_id, user_id))
    conn.commit()
    points = c.execute("SELECT points FROM rankings WHERE user_id = ?", (user_id,)).fetchone()[0]

    sub_channel = bot.get_channel(SUBMISSIONS_CHANNEL_ID)
    if sub_channel:
        message = await sub_channel.send(f"📥 **Submission from {ctx.author.mention}**:\n{link}")
        await message.create_thread(name=f"{ctx.author.name}'s Loop")

    await ctx.send(f"✅ Submission accepted! You now have {points} points.")

@bot.command()
async def rank(ctx):
    user_id = str(ctx.author.id)
    result = c.execute("SELECT points FROM rankings WHERE user_id = ?", (user_id,)).fetchone()
    points = result[0] if result else 0
    await ctx.send(f"📊 {ctx.author.mention}, you have **{points}** points.")

@bot.command()
async def leaderboard(ctx):
    c.execute("SELECT user_id, points FROM rankings ORDER BY points DESC LIMIT 5")
    top = c.fetchall()
    text = "🏆 **Top 5 Creators:**\n" + "\n".join(
        [f"{i+1}. <@{user}> – {pts} pts" for i, (user, pts) in enumerate(top)]
    )
    await ctx.send(text)

@bot.command()
@commands.has_permissions(administrator=True)
async def postprompt(ctx):
    prompt = await get_prompt()
    await ctx.send(f"🎯 **Today's Creative Challenge:**\n{prompt}")

@postprompt.error
async def postprompt_error(ctx, error):
    # Handle missing-permissions error cleanly
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permissions to use this command.")
    else:
        raise error

# Reaction-based voting
@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id == SUBMISSIONS_CHANNEL_ID and payload.emoji.name == "👍":
        user_id = str(payload.user_id)
        c.execute("INSERT OR REPLACE INTO rankings (user_id, points) VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + 1)", (user_id, user_id))
        conn.commit()

        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        channel = bot.get_channel(payload.channel_id)
        if channel and member:
            await channel.send(f"🗳️ {member.mention} voted! +1 point.")

# Run bot
bot.run(TOKEN)
