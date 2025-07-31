import os
import discord
import asyncio
import sqlite3
import itertools
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, time as dtime

import openai
import sys
import random

# Load environment variables
# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')
# Determine if we're running in single-run mode (cron) vs. normal loop
_RUN_MODE = sys.argv[1] if len(sys.argv) > 1 else None
# Enable or disable the built-in scheduling (set RUN_SCHEDULE=false to rely on external cron)
_RUN_SCHEDULE = os.getenv('RUN_SCHEDULE', 'true').lower() not in ('false', '0', 'no')

# Schedule times for internal tasks (24h format), configurable via .env
DAILY_HOUR = int(os.getenv('DAILY_HOUR', '4'))
DAILY_MINUTE = int(os.getenv('DAILY_MINUTE', '0'))
LEADERBOARD_HOUR = int(os.getenv('LEADERBOARD_HOUR', '4'))
LEADERBOARD_MINUTE = int(os.getenv('LEADERBOARD_MINUTE', '5'))

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Bot initialization
bot = commands.Bot(command_prefix='!', intents=intents)

# Channel and category IDs (update with your server's IDs)
# Central ID table:
# rules: 1396655144804024380
# moderator-only: 1396655144804024383
# voice: 1394026685975887993
# Start Here category: 1393758933146931280
# general: 1393758933146931282
# welcome: 1393807671525773322
# how-it-works: 1393807869299789954
# Daily Loop category: 1393808136133148692
# current-challenge: 1393808509463691294
# submissions: 1393808617354035321
# voting-hall: 1393808682407428127
# Creative Zone category: 1393809063665467402
# visual-art: 1393809187531919360
# beat-loops: 1393809294079819917
# short-fiction: 1393809404473774151
# poetry: 1393809488909439118
# photo-snaps: 1393809600821592114
# experimental: 1393809801267515484
# Feedback & Growth category: 1393810216163741716
# critique-corner: 1393810379032760471
# resources-and-tips: 1393810535644139590
# ai-tools: 1393810714052792432
# Rankings + Events category: 1393810822941114428
# leaderboard: 1393810922396585984
# past-winners: 1393810993426989099
# season-announcements: 1393811080442024067
# Community category: 1393811267734736976
# general-chat: 1393811389579268206
# introductions: 1393811501013536889
# memes-and-vibes: 1393811645922545745
# music-share: 1393811741715988540

RULES_CHANNEL_ID = 1396655144804024380
MODERATOR_ONLY_CHANNEL_ID = 1396655144804024383
VOICE_CATEGORY_ID = 1394026685975887993
CHALLENGE_CHANNEL_ID = 1393808509463691294  # current-challenge
SUBMISSIONS_CHANNEL_ID = 1393808617354035321 # submissions
LEADERBOARD_CHANNEL_ID = 1393810922396585984 # leaderboard
WELCOME_CHANNEL_ID = 1393807671525773322     # welcome
HOW_IT_WORKS_CHANNEL_ID = 1393807869299789954 # how-it-works

# SQLite DB setup
conn = sqlite3.connect('rankings.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS rankings (
    user_id TEXT PRIMARY KEY,
    points INTEGER
)''')
conn.commit()

# Static fallback prompts (shuffled to vary order)
_fallback_prompts = [
    "🌿 Create a loop inspired by nature's rhythm.",
    "💭 Make something based on a dream you had.",
    "🚀 Design a sound/scene/story from the future.",
    "🌀 Loop based on the feeling of déjà vu.",
    "🔥 Create something chaotic, messy, raw."
]
random.shuffle(_fallback_prompts)
static_prompts = itertools.cycle(_fallback_prompts)

# Generate a prompt using GPT
async def generate_ai_prompt():
    try:
        response = openai.ChatCompletion.acreate(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a creative challenge bot that generates short, unique prompts for music, art, or storytelling."},
                {"role": "user", "content": "Give me a short, vivid creative challenge prompt for my Discord community."}
            ],
                max_tokens=50,
            temperature=0.70
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
            post_daily_leaderboard.start()
        except RuntimeError:
            pass
    else:
        print(
            "🕒 Automatic scheduling disabled (RUN_SCHEDULE=false); skipping daily loop startup."
        )

## Scheduled posts
@tasks.loop(time=dtime(hour=DAILY_HOUR, minute=DAILY_MINUTE))
async def post_daily_challenge():
    """Post the daily creative prompt at the configured time."""
    channel = bot.get_channel(CHALLENGE_CHANNEL_ID)
    if channel:
        prompt = await get_prompt()
        await channel.send(f"🎯 **Daily Challenge**:\n{prompt}")
    else:
        print("⚠️ Challenge channel not found. Check CHALLENGE_CHANNEL_ID.")

@tasks.loop(time=dtime(hour=LEADERBOARD_HOUR, minute=LEADERBOARD_MINUTE))
async def post_daily_leaderboard():
    """Post the daily top-5 leaderboard at the configured time."""
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
    else:
        print("⚠️ Leaderboard channel not found. Check LEADERBOARD_CHANNEL_ID.")

# Commands
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

@bot.command(name='commands')
async def list_commands(ctx):
    await ctx.send(
        "📜 Commands: `!ping`, `!how`, `!submit <link>` or attach a file, `!vote <1-10>`, `!rank`, `!leaderboard`, `!postprompt`"
    )

@bot.command(name='how')
async def how(ctx):
    """Explain how to participate in the daily creative challenge."""
    how_text = (
        "👋 **How to use LoopBot:**\n"
        "1. Each morning, check the daily challenge in the designated channel or with `!postprompt`.\n"
        "2. Create your work and submit it with `!submit <link>` or attach a media file (audio/image/video).\n"
        "3. Earn 1 point per submission and bonus points for 👍 reactions.\n"
        "4. View your score with `!rank` and the top creators with `!leaderboard`.\n"
        "5. Administrators can manually post a prompt using `!postprompt`.\n"
        "6. Use `!ping` to check if I'm alive!"
    )
    await ctx.send(how_text)

@bot.command()
async def submit(ctx, link: str = None):
    """Accept a URL or an attached audio file (.mp3, .wav, .m4a) as a submission and award points."""
    attachments = ctx.message.attachments
    # Attachment path: accept any file (audio/image/video/etc.)
    if attachments:
        att = attachments[0]
        uid = str(ctx.author.id)
        c.execute(
            "INSERT OR REPLACE INTO rankings (user_id, points) "
            "VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + 1)",
            (uid, uid),
        )
        conn.commit()
        points = c.execute("SELECT points FROM rankings WHERE user_id = ?", (uid,)).fetchone()[0]
        sub_ch = bot.get_channel(SUBMISSIONS_CHANNEL_ID)
        if sub_ch:
            file = await att.to_file()
            await sub_ch.send(f"📥 **File Submission from {ctx.author.mention}:**", file=file)
        await ctx.send(f"✅ Submission accepted! You now have {points} points.")
        return
    # URL submission path
    if not link:
        await ctx.send("❌ Please provide a link or attach a file.")
        return
    uid = str(ctx.author.id)
    c.execute(
        "INSERT OR REPLACE INTO rankings (user_id, points) "
        "VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + 1)",
        (uid, uid),
    )
    conn.commit()
    points = c.execute("SELECT points FROM rankings WHERE user_id = ?", (uid,)).fetchone()[0]
    sub_ch = bot.get_channel(SUBMISSIONS_CHANNEL_ID)
    if sub_ch:
        await sub_ch.send(f"📥 **Link Submission from {ctx.author.mention}:** {link}")
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

@bot.command(name='vote')
async def vote(ctx, score: int):
    """Cast a 1–10 vote for the submission associated with this thread."""
    thread = ctx.channel
    sub = None
    # Check link-submissions
    if hasattr(thread, 'parent_id') and thread.parent_id:
        c.execute("SELECT id FROM link_submissions WHERE thread_id = ?", (thread.id,))
        row = c.fetchone()
        sub = ('link', row[0]) if row else None
        if not sub:
            c.execute("SELECT id FROM audio_submissions WHERE thread_id = ?", (thread.id,))
            row = c.fetchone()
            sub = ('audio', row[0]) if row else None
    if not sub:
        await ctx.send("❌ You can only vote inside a submission thread.")
        return
    if not 1 <= score <= 10:
        await ctx.send("❌ Please vote with a score between 1 and 10.")
        return
    sub_id = sub[1]
    uid = str(ctx.author.id)
    try:
        c.execute(
            "INSERT INTO votes (user_id, submission_id, score) VALUES (?, ?, ?)",
            (uid, sub_id, score)
        )
        conn.commit()
        await ctx.send(f"✅ Your vote of {score} has been recorded.")
    except sqlite3.IntegrityError:
        await ctx.send("❌ You have already voted for this submission.")

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

## Welcome new members

@bot.event
async def on_member_join(member):
    """Send a welcome message to newcomers, linking key channels."""
    # Challenge channel (current challenge) and welcome channel
    challenge_chan = bot.get_channel(CHALLENGE_CHANNEL_ID)
    welcome_chan = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_chan:
        text = (
            f"🎉 Welcome {member.mention}! Please introduce yourself here so we can get to know you.\n"
            f"Also, check out the current challenge in {challenge_chan.mention} and have fun making something new!"
        )
        await welcome_chan.send(text)


# Reaction-based voting
@bot.event
async def on_raw_reaction_add(payload):
    if payload.channel_id == SUBMISSIONS_CHANNEL_ID and payload.emoji.name == "👍":
        user_id = str(payload.user_id)
        c.execute(
            "INSERT OR REPLACE INTO rankings (user_id, points) VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + 1)",
            (user_id, user_id),
        )
        conn.commit()

        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        channel = bot.get_channel(payload.channel_id)
        if channel and member:
            await channel.send(f"🗳️ {member.mention} voted! +1 point.")

# Allow raw file or link posts in submissions channel as submissions
@bot.event
async def on_message(message):
    """Allow raw file or link posts in submissions channel as submissions."""
    # Process commands first (so !submit still works)
    await bot.process_commands(message)
    # Ignore bots and non-submissions channels or prefixed commands
    if (
        message.author.bot
        or message.channel.id != SUBMISSIONS_CHANNEL_ID
        or message.content.startswith(bot.command_prefix)
    ):
        return

    uid = str(message.author.id)
    # Attachment submission (auto-create thread and record)
    if message.attachments:
        att = message.attachments[0]
        # Record submission metadata
        now_iso = datetime.utcnow().isoformat()
        c.execute(
            "INSERT INTO audio_submissions (user_id, filename, timestamp) VALUES (?, ?, ?)",
            (uid, att.filename, now_iso)
        )
        sub_id = c.lastrowid
        conn.commit()
        # Award point
        c.execute(
            "INSERT OR REPLACE INTO rankings (user_id, points) "
            "VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + 1)",
            (uid, uid),
        )
        conn.commit()
        points = c.execute("SELECT points FROM rankings WHERE user_id = ?", (uid,)).fetchone()[0]
        # Post and thread
        chan = message.channel
        sent = await chan.send(f"📥 **File Submission from {message.author.mention}:**", file=await att.to_file())
        thread = await sent.create_thread(name=f"{message.author.name}'s submission")
        c.execute("UPDATE audio_submissions SET thread_id = ? WHERE id = ?", (thread.id, sub_id))
        conn.commit()
        await chan.send(f"✅ Submission accepted! You now have {points} points.")
        return

    # Link submission (auto-create thread and record)
    link = message.content.strip()
    if link:
        now_iso = datetime.utcnow().isoformat()
        c.execute(
            "INSERT INTO link_submissions (user_id, link, timestamp, tags) VALUES (?, ?, ?, '')",
            (uid, link, now_iso)
        )
        sub_id = c.lastrowid
        conn.commit()
        # Award point
        c.execute(
            "INSERT OR REPLACE INTO rankings (user_id, points) "
            "VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + 1)",
            (uid, uid),
        )
        conn.commit()
        points = c.execute("SELECT points FROM rankings WHERE user_id = ?", (uid,)).fetchone()[0]
        chan = message.channel
        sent = await chan.send(f"📥 **Link Submission from {message.author.mention}:** {link}")
        thread = await sent.create_thread(name=f"{message.author.name}'s submission")
        c.execute("UPDATE link_submissions SET thread_id = ? WHERE id = ?", (thread.id, sub_id))
        conn.commit()
        await chan.send(f"✅ Submission accepted! You now have {points} points.")

# Run bot
bot.run(TOKEN)
