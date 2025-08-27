import os
import discord
import asyncio
import sqlite3
import itertools
import aiohttp
from discord.ext import commands, tasks
from dotenv import load_dotenv
import logging
from datetime import datetime, time as dtime, timezone, timedelta

import openai
from openai import OpenAIError
# Async OpenAI client for v1.x API (sync methods run via asyncio.to_thread)
client = openai.OpenAI()
from agents import trace
import sys
import random
import re

from bs4 import BeautifulSoup
import base64, csv
import math

# Nitter instances (fallback) for lightweight Twitter scraping
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.snopyta.org",
    "https://nitter.1d4.us",
]

# Number of memes to fetch per scrape
SCRAPE_LIMIT = 25

# Nitter instances (fallback) for lightweight Twitter scraping
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.snopyta.org",
    "https://nitter.1d4.us",
]

# Load environment variables
# Load environment variables
# Initialize debug logging for Spotify auth troubleshooting
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()
# Directory for helper scripts
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scripts')
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    print("❌ ERROR: DISCORD_BOT_TOKEN environment variable is missing.")
    sys.exit(1)
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
# Voting summary schedule (default shortly after leaderboard)
# Voting summary schedule (24h UTC), configurable via .env
VOTE_SUMMARY_HOUR = int(os.getenv('VOTE_SUMMARY_HOUR', '0'))
VOTE_SUMMARY_MINUTE = int(os.getenv('VOTE_SUMMARY_MINUTE', '0'))
# Crypto price update interval in hours (default: every hour)
CRYPTO_INTERVAL_HOURS = int(os.getenv('CRYPTO_INTERVAL_HOURS', '1'))
# Voting lock window (hours) after submission; votes outside this window are ignored
VOTE_WINDOW_HOURS = int(os.getenv('VOTE_WINDOW_HOURS', '24'))
# Live crypto update interval in seconds for scrolling ticker (via !livecrypto)
CRYPTO_LIVE_INTERVAL = int(os.getenv('CRYPTO_LIVE_INTERVAL', '5'))
# Optional role IDs to assign upon reaching certain levels
XP_ROLE_L3 = int(os.getenv('XP_ROLE_L3', '0')) or None
XP_ROLE_L5 = int(os.getenv('XP_ROLE_L5', '0')) or None
XP_ROLE_L10 = int(os.getenv('XP_ROLE_L10', '0')) or None

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
VOTING_HALL_CHANNEL_ID = 1393808682407428127 # voting-hall
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
## Community category
# music-share: 1393811741715988540
MUSIC_SHARE_CHANNEL_ID = 1393811741715988540  # music-share
## community category
MUSIC_SHARE_CHANNEL_ID = 1393811741715988540  # music-share
RULES_CHANNEL_ID = 1396655144804024380
MODERATOR_ONLY_CHANNEL_ID = 1396655144804024383
VOICE_CATEGORY_ID = 1394026685975887993
CHALLENGE_CHANNEL_ID = 1393808509463691294  # current-challenge
SUBMISSIONS_CHANNEL_ID = 1393808617354035321 # submissions
VOTING_HALL_CHANNEL_ID = 1393808682407428127 # voting-hall
LEADERBOARD_CHANNEL_ID = 1393810922396585984 # leaderboard
CRYPTO_CHANNEL_ID = 1401992445251817472      # crypto price tracker
WELCOME_CHANNEL_ID = 1393807671525773322     # welcome
HOW_IT_WORKS_CHANNEL_ID = 1393807869299789954 # how-it-works
MEMES_CHANNEL_ID = 1393811645922545745       # memes-and-vibes

## SQLite DB setup
## SQLite DB setup
## Persistent storage detection: prefer env var, else auto‑detect mounted /data or LoopBot/data
# Persistent storage detection: env var or mounted /data, else fallback to LoopBot/data
_env_data = os.getenv('RAILWAY_PERSISTENT_DIR') or os.getenv('DATA_DIR')
_vol_data = '/data' if os.path.isdir('/data') else None
_local_data = (
    os.path.join(os.getcwd(), 'LoopBot', 'data')
    if os.path.isdir(os.path.join(os.getcwd(), 'LoopBot', 'data'))
    else None
)
persistent_dir = _env_data or _vol_data or _local_data
# Debug: verify which directory is used for persistence
print(f"🔍 Persistent dir is: {persistent_dir}")
if persistent_dir and os.path.isdir(persistent_dir):
    try:
        print(f"📂 Volume contents: {sorted(os.listdir(persistent_dir))}")
    except Exception:
        pass
explicit_db = os.getenv('DB_PATH')
if persistent_dir:
    # Ensure the persistent directory exists
    os.makedirs(persistent_dir, exist_ok=True)
    # Seed the persistent volume from a bundled local backup on first run
    vol_file = os.path.join(persistent_dir, 'rankings.db')
    if not os.path.exists(vol_file) and os.path.exists(os.path.join(os.getcwd(), 'rankings.db')):
        import shutil

        shutil.copy(
            os.path.join(os.getcwd(), 'rankings.db'),
            vol_file,
        )
    DB_PATH = explicit_db or vol_file
else:
    # No persistent volume: allow explicit DB_PATH or fallback to in-repo rankings.db if present
    if explicit_db:
        DB_PATH = explicit_db
    elif os.path.exists(os.path.join(os.getcwd(), 'rankings.db')):
        # Use committed in-repo database (ephemeral container storage)
        DB_PATH = os.path.join(os.getcwd(), 'rankings.db')
    else:
        print(
            "❌ ERROR: No persistent volume at /data, and no DB_PATH set.\n"
            "Commit a rankings.db to the repo root or configure DB_PATH to enable data persistence."
        )
        sys.exit(1)

# Ensure parent directory exists before opening the SQLite database
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS rankings (
    user_id TEXT PRIMARY KEY,
    points INTEGER
)''')
conn.commit()

# Create submissions and votes tables (include tags/orig_message_id/timestamp columns)
c.execute('''CREATE TABLE IF NOT EXISTS audio_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    filename TEXT,
    timestamp TEXT,
    thread_id INTEGER,
    message_id INTEGER,
    orig_message_id INTEGER,
    tags TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS link_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    link TEXT,
    timestamp TEXT,
    tags TEXT,
    thread_id INTEGER,
    message_id INTEGER,
    orig_message_id INTEGER
)''')
c.execute('''CREATE TABLE IF NOT EXISTS votes (
    user_id TEXT,
    submission_id INTEGER,
    score INTEGER,
    timestamp TEXT,
    PRIMARY KEY(user_id, submission_id)
)''')
conn.commit()

## XP & leveling tables
c.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    last_xp_ts TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS xp_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    delta INTEGER,
    reason TEXT,
    ts TEXT
)''')

## Streak tracking table
c.execute('''CREATE TABLE IF NOT EXISTS streaks (
    user_id TEXT PRIMARY KEY,
    current INTEGER DEFAULT 0,
    best INTEGER DEFAULT 0,
    last_date TEXT
)''')

## Optional DM reminders opt-in
c.execute('''CREATE TABLE IF NOT EXISTS reminders (
    user_id TEXT PRIMARY KEY
)''')
conn.commit()

# Migrate existing tables to add missing columns if needed
try:
    c.execute('ALTER TABLE audio_submissions ADD COLUMN tags TEXT')
    c.execute('ALTER TABLE audio_submissions ADD COLUMN orig_message_id INTEGER')
    c.execute('ALTER TABLE link_submissions ADD COLUMN tags TEXT')
    c.execute('ALTER TABLE link_submissions ADD COLUMN orig_message_id INTEGER')
    c.execute('ALTER TABLE votes ADD COLUMN timestamp TEXT')
    conn.commit()
except sqlite3.OperationalError:
    pass

# Messages & voting v2 tables
c.execute('''CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    author_id TEXT,
    timestamp TEXT
)''')
c.execute('''CREATE TABLE IF NOT EXISTS message_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    voter_id TEXT,
    score INTEGER,
    ts TEXT,
    UNIQUE(message_id, voter_id)
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
        data = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "You are a creative challenge bot. Provide concise, vivid, and self-contained prompts "
                    "in complete sentences that inspire music, art, or storytelling."
                )},
                {"role": "user", "content": (
                    "Please give me a creative challenge prompt: one or two clear, vivid sentences."
                )}
            ],
            max_tokens=100,
            temperature=0.7,
            frequency_penalty=0.5,
            presence_penalty=0.0,
        )
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
            post_vote_summary.start()
            crypto_price_tracker.start()
        except RuntimeError:
            pass
    else:
        print(
            "🕒 Automatic scheduling disabled (RUN_SCHEDULE=false); skipping daily loop startup."
        )

## Scheduled posts
@tasks.loop(time=dtime(hour=DAILY_HOUR, minute=DAILY_MINUTE, tzinfo=timezone.utc))
async def post_daily_challenge():
    """Post the daily creative prompt at the configured time."""
    channel = bot.get_channel(CHALLENGE_CHANNEL_ID)
    if channel:
        # Send DM reminders to opted-in users before the daily challenge
        c.execute("SELECT user_id FROM reminders")
        for (uid,) in c.fetchall():
            user = bot.get_user(int(uid))
            if user:
                try:
                    await user.send(
                        "🔔 Reminder: don't forget to submit today's creative challenge!"
                    )
                except Exception:
                    pass

        prompt = await get_prompt()
        # Post daily prompt as an embed for richer formatting
        embed = discord.Embed(
            title="🎯 Daily Creative Challenge",
            description=prompt,
            color=discord.Color.blue(),
        )
        # Optional: set a banner image via env var (DAILY_BANNER_URL)
        banner = os.getenv('DAILY_BANNER_URL')
        if banner:
            embed.set_image(url=banner)
        await channel.send(embed=embed)
    else:
        print("⚠️ Challenge channel not found. Check CHALLENGE_CHANNEL_ID.")

@tasks.loop(time=dtime(hour=LEADERBOARD_HOUR, minute=LEADERBOARD_MINUTE, tzinfo=timezone.utc))
async def post_daily_leaderboard():
    """Post the daily top-5 leaderboard at the configured UTC time."""
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if channel:
        # Exclude the bot user from the leaderboard
        bot_id = str(bot.user.id)
        c.execute(
            "SELECT user_id, points FROM rankings WHERE user_id != ? "
            "ORDER BY points DESC LIMIT 5",
            (bot_id,)
        )
        top = c.fetchall()
        if top:
            embed = discord.Embed(
                title="🏆 Top 5 Creators:",
                color=discord.Color.gold(),
            )
            # add each entry as a field
            for i, (user, pts) in enumerate(top, start=1):
                embed.add_field(
                    name=f"#{i}",
                    value=f"<@{user}> – {pts} pts",
                    inline=False,
                )
            # Optional thumbnail or server icon
            # embed.set_thumbnail(url=channel.guild.icon_url)
            await channel.send(embed=embed)
    else:
        print("⚠️ Leaderboard channel not found. Check LEADERBOARD_CHANNEL_ID.")

@tasks.loop(time=dtime(hour=VOTE_SUMMARY_HOUR, minute=VOTE_SUMMARY_MINUTE, tzinfo=timezone.utc))
async def post_vote_summary():
    """Post a daily summary of top-voted submissions in the voting-hall channel."""
    channel = bot.get_channel(VOTING_HALL_CHANNEL_ID)
    if channel:
        # Trending = votes cast in the last VOTE_WINDOW_HOURS
        since = datetime.now(timezone.utc) - timedelta(hours=VOTE_WINDOW_HOURS)
        threshold = since.isoformat()
        c.execute(
            "SELECT message_id, SUM(score) AS total FROM message_votes "
            "WHERE ts >= ? GROUP BY message_id "
            "ORDER BY total DESC LIMIT 5",
            (threshold,)
        )
        rows = c.fetchall()
        if not rows:
            await channel.send("🏅 No votes have been cast in the recent window.")
            return
        embed = discord.Embed(
            title="📈 Trending: Top 5 in last {VOTE_WINDOW_HOURS}h",
            color=discord.Color.green(),
        )
        for i, (msg_id, total) in enumerate(rows, start=1):
            try:
                msg = await channel.fetch_message(msg_id)
                label = f"[View submission]({msg.jump_url})"
            except Exception:
                label = f"Submission #{msg_id}"
            embed.add_field(
                name=f"{i}. {label}",
                value=f"Total: {total} votes",
                inline=False,
            )
        await channel.send(embed=embed)
    else:
        print("⚠️ Voting hall channel not found. Check VOTING_HALL_CHANNEL_ID.")



@tasks.loop(
    time=[
        dtime(hour=h, minute=m, tzinfo=timezone.utc)
        for h in range(24)
        for m in (0, 15, 30, 45)
    ]
)
async def crypto_price_tracker():
    """Fetch and post top cryptocurrencies by market cap at each quarter-hour UTC."""
    channel = bot.get_channel(CRYPTO_CHANNEL_ID)
    if not channel:
        print("⚠️ Crypto channel not found. Check CRYPTO_CHANNEL_ID.")
        return
    # Select specific coins by ID for live tickers
    tickers = os.getenv('CRYPTO_TICKERS', 'bitcoin,ethereum,ripple,solana')
    ids = ','.join([t.strip() for t in tickers.split(',') if t.strip()])
    markets_url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(markets_url) as resp:
            data = await resp.json()
    if not data:
        print("⚠️ Failed to fetch crypto market data.")
        return
    # Send one embed per coin with price as title (large) and colored by 24h change
    now = datetime.now(timezone.utc)
    for coin in data:
        if not isinstance(coin, dict):
            continue
        sym = coin.get('symbol', '').upper()
        pr = coin.get('current_price')
        p1 = coin.get('price_change_percentage_1h_in_currency')
        p24 = coin.get('price_change_percentage_24h_in_currency')
        p7 = coin.get('price_change_percentage_7d_in_currency')
        # Format helpers
        def fmt(val):
            if val is None:
                return '—'
            sign = '+' if val >= 0 else ''
            arrow = '📈' if val >= 0 else '📉'
            return f"{arrow} {sign}{val:.2f}%"
        price_str = f"${pr:,.2f}" if pr is not None else '—'
        # Build markdown table for changes
        desc = (
            '| 1h | 24h | 7d |\n'
            '|:---:|:---:|:---:|\n'
            f'| {fmt(p1)} | {fmt(p24)} | {fmt(p7)} |'
        )
        # Color embed based on 24h change
        color = discord.Color.green() if p24 and p24 >= 0 else discord.Color.red()
        title = f"{sym} — {price_str}"
        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
            timestamp=now,
        )
        embed.set_footer(text='Data provided by CoinGecko')
        # Thumbnail icon if available
        if coin.get('image'):
            embed.set_thumbnail(url=coin['image'])
        await channel.send(embed=embed)
        await asyncio.sleep(1)

def _make_ticker_embed(coin: dict) -> discord.Embed:
    """Helper to build a single crypto embed for live updates."""
    now = datetime.now(timezone.utc)
    symbol = coin.get('symbol', '').upper()
    name = coin.get('name', '').title()
    price = coin.get('current_price')
    change24 = coin.get('price_change_percentage_24h')
    arrow = '📈' if change24 and change24 >= 0 else '📉'
    description = (
        f"**Price:** ${price:,.2f}\n"
        f"**24h Change:** {arrow} {change24:+.2f}%"
        if price is not None and change24 is not None
        else "Price data unavailable"
    )
    embed = discord.Embed(
        title=f"{symbol} — {name}",
        description=description,
        color=discord.Color.dark_blue(),
        timestamp=now,
    )
    if coin.get('image'):
        embed.set_thumbnail(url=coin['image'])
    embed.set_footer(text="Data by CoinGecko")
    return embed

@bot.command(name='livecrypto')
async def livecrypto(ctx):
    """Post live-updating embeds for configured crypto tickers (updates every CRYPTO_LIVE_INTERVAL seconds)."""
    tickers = os.getenv('CRYPTO_TICKERS', 'bitcoin,ethereum,ripple,solana')
    ids = ','.join(t.strip() for t in tickers.split(',') if t.strip())
    url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=market_cap_desc&sparkline=false"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
    if not data:
        return await ctx.send("⚠️ Failed to fetch crypto data.")
    # Send initial embeds and keep references
    msgs = {}
    for coin in data:
        embed = _make_ticker_embed(coin)
        msg = await ctx.send(embed=embed)
        msgs[coin.get('id')] = msg
        await asyncio.sleep(1)
    await ctx.send(f"🔁 Live crypto tracker started (updates every {CRYPTO_LIVE_INTERVAL}s)")

    async def updater():
        async with aiohttp.ClientSession() as session:
            while True:
                await asyncio.sleep(CRYPTO_LIVE_INTERVAL)
                async with session.get(url) as resp:
                    newdata = await resp.json()
                for coin in newdata:
                    # skip malformed entries
                    if not isinstance(coin, dict):
                        continue
                    msg = msgs.get(coin.get('id'))
                    if msg:
                        new_embed = _make_ticker_embed(coin)
                        await msg.edit(embed=new_embed)

    bot.loop.create_task(updater())


# XP & leveling: accrue XP on messages (1 XP per 60s), track levels, assign roles
@bot.event
async def on_message(message):
    # Record any new submission (attachments) in the submissions channel
    if message.channel.id == SUBMISSIONS_CHANNEL_ID and message.attachments and not message.author.bot:
        try:
            c.execute(
                "INSERT OR IGNORE INTO messages(message_id, channel_id, author_id, timestamp) VALUES(?,?,?,?)",
                (
                    message.id,
                    message.channel.id,
                    str(message.author.id),
                    message.created_at.replace(tzinfo=timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        except Exception as e:
            print(f"⚠️ Failed to record submission message: {e}")

    # Ignore bots and blacklisted channels for XP & voting logic
    if message.author.bot:
        return
    if message.channel.id in (RULES_CHANNEL_ID, MODERATOR_ONLY_CHANNEL_ID):
        return
    now = datetime.now(timezone.utc)
    user_id = str(message.author.id)
    # Fetch or initialize user record
    c.execute("SELECT xp, level, last_xp_ts FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if row:
        xp, lvl, last_ts = row
        last_ts = datetime.fromisoformat(last_ts) if last_ts else None
    else:
        xp, lvl, last_ts = 0, 0, None
    # Award XP if last award was over 60 seconds ago
    if last_ts is None or (now - last_ts).total_seconds() >= 60:
        new_xp = xp + 1
        new_lvl = int(0.1 * math.sqrt(new_xp))
        # Upsert user XP and level
        c.execute(
            "INSERT INTO users(user_id, xp, level, last_xp_ts) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET xp=excluded.xp, level=excluded.level, last_xp_ts=excluded.last_xp_ts",
            (user_id, new_xp, new_lvl, now.isoformat()),
        )
        # Record event
        c.execute(
            "INSERT INTO xp_events(user_id, delta, reason, ts) VALUES(?,?,?,?)",
            (user_id, 1, "message", now.isoformat()),
        )
        conn.commit()
        # Assign level-up role if configured
        if new_lvl > lvl:
            try:
                role_id = None
                if new_lvl >= 10 and XP_ROLE_L10:
                    role_id = XP_ROLE_L10
                elif new_lvl >= 5 and XP_ROLE_L5:
                    role_id = XP_ROLE_L5
                elif new_lvl >= 3 and XP_ROLE_L3:
                    role_id = XP_ROLE_L3
                if role_id:
                    role = message.guild.get_role(role_id)
                    if role:
                        await message.author.add_roles(role, reason="Level up")
            except Exception as e:
                print(f"⚠️ Failed to assign level role: {e}")
    # Continue with other commands and events
    await bot.process_commands(message)

# Commands
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")


@bot.command()
async def streak(ctx):
    """Show your current and best daily submission streak."""
    user_id = str(ctx.author.id)
    c.execute(
        "SELECT current, best FROM streaks WHERE user_id = ?", (user_id,)
    )
    row = c.fetchone()
    if not row:
        await ctx.send("🔸 You have no recorded streak yet. Submit something to start your streak!")
        return
    current, best = row
    await ctx.send(f"🔸 Current streak: {current} days. Best streak: {best} days.")


@bot.command()
async def streakboard(ctx):
    """Show top current streaks among all users."""
    c.execute(
        "SELECT user_id, current, best FROM streaks ORDER BY current DESC LIMIT 5"
    )
    rows = c.fetchall()
    if not rows:
        await ctx.send("🔸 No streaks recorded yet.")
        return
    text = "🏅 Top 5 Current Streaks:"
    for i, (uid, current, best) in enumerate(rows, start=1):
        text += f"\n{i}. <@{uid}> — {current} days (best: {best})"
    await ctx.send(text)


@bot.command()
async def remindme(ctx):
    """Opt in to receive a daily DM reminder to submit the challenge."""
    user_id = str(ctx.author.id)
    c.execute("SELECT 1 FROM reminders WHERE user_id = ?", (user_id,))
    if c.fetchone():
        c.execute("DELETE FROM reminders WHERE user_id = ?", (user_id,))
        conn.commit()
        await ctx.send("🔕 You have been unsubscribed from daily reminders.")
    else:
        c.execute("INSERT INTO reminders(user_id) VALUES(?)", (user_id,))
        conn.commit()
        await ctx.send("🔔 You are now subscribed to daily reminders.")


@bot.event
async def on_reaction_add(reaction, user):
    """Quick vote via 👍 or ⭐ reactions on submissions or on voting-hall messages."""
    if user.bot:
        return
    msg = reaction.message
    if msg.channel.id not in (SUBMISSIONS_CHANNEL_ID, VOTING_HALL_CHANNEL_ID):
        return
    if str(reaction.emoji) not in ("👍", "⭐"):
        return
    # Determine original submission timestamp from messages or submissions tables
    c.execute("SELECT timestamp FROM messages WHERE message_id = ?", (msg.id,))
    row = c.fetchone()
    if not row:
        c.execute(
            "SELECT timestamp FROM audio_submissions WHERE message_id = ?",
            (msg.id,),
        )
        row = c.fetchone()
    if not row:
        c.execute(
            "SELECT timestamp FROM link_submissions WHERE message_id = ?",
            (msg.id,),
        )
        row = c.fetchone()
    if not row:
        return
    msg_ts = datetime.fromisoformat(row[0])
    if (datetime.now(timezone.utc) - msg_ts).total_seconds() > VOTE_WINDOW_HOURS * 3600:
        return
    try:
        c.execute(
            "INSERT INTO message_votes(message_id, voter_id, score, ts) VALUES(?,?,?,?)",
            (msg.id, str(user.id), 1, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass


@bot.event
async def on_reaction_remove(reaction, user):
    """Remove quick-vote if a 👍 or ⭐ reaction is removed."""
    if user.bot:
        return
    msg = reaction.message
    if msg.channel.id not in (SUBMISSIONS_CHANNEL_ID, VOTING_HALL_CHANNEL_ID):
        return
    if str(reaction.emoji) not in ("👍", "⭐"):
        return
    try:
        c.execute(
            "DELETE FROM message_votes WHERE message_id = ? AND voter_id = ? AND score = 1",
            (msg.id, str(user.id)),
        )
        conn.commit()
    except Exception:
        pass

@bot.command(name='commands')
async def list_commands(ctx):
    await ctx.send(
        "📜 Commands: `!ping`, `!how`, `!submit <link>` or attach a file, `!vote <1-10>`, `!rank`, `!leaderboard`, `!chat <msg>`, `!search #tag`, `!music [track|album|artist] <search terms>`, `!gif <search terms>`"
    )

@bot.command(name='how')
async def how(ctx):
    """Explain how to participate in the daily creative challenge."""
    how_text = (
        "👋 **How to use LoopBot:**\n"
        "1. Each morning, check the daily challenge in the designated channel or with `!postprompt`.\n"
        "2. Create your work and submit it with `!submit <link>` or attach a file (audio/image/video/other).\n"
        "3. Earn 1 point per submission and bonus points for 👍 reactions.\n"
        "4. View your score with `!rank` and the top creators with `!leaderboard`.\n"
        "5. Administrators can manually post a prompt using `!postprompt`.\n"
        "6. Use `!ping` to check if I'm alive!"
    )
    await ctx.send(how_text)

@bot.command()
async def submit(ctx, link: str = None):
    """Submit a URL or attach a file (image/video/audio/etc.) to the submissions channel."""
    # Determine content to forward: reply, attachment, or provided link
    ref = ctx.message.reference
    attachments = None
    if ref and ref.message_id:
        ref_chan = bot.get_channel(ref.channel_id) or ctx.channel
        ref_msg = await ref_chan.fetch_message(ref.message_id)
        if ref_msg.author != ctx.author:
            return await ctx.send("❌ You can only submit your own messages.")
        attachments = ref_msg.attachments
        link = None if attachments else ref_msg.content.strip()
    else:
        attachments = ctx.message.attachments
    # Fallback: find recent self-attachments if none on this message
    if not attachments and not link:
        async for prev in ctx.channel.history(limit=10, before=ctx.message):
            if prev.author == ctx.author and prev.attachments:
                attachments = prev.attachments
                break

    # Post directly to voting hall so members can vote immediately
    voting_chan = bot.get_channel(VOTING_HALL_CHANNEL_ID)
    if not voting_chan:
        return await ctx.send("❌ Voting hall channel not found. Check configuration.")

    # Forward to voting hall with pre-added vote reactions
    # extract any tags from message content (e.g. #tag)
    tag_list = [w.lstrip('#') for w in (link or '').split() if w.startswith('#')]
    tags = ' '.join(tag_list)
    if attachments:
        content = f"📥 Submission from {ctx.author.mention}"
        if tags:
            content += "  " + " ".join(f"#{t}" for t in tag_list)
        sent = await voting_chan.send(content, file=await attachments[0].to_file())
    elif link:
        content = f"📥 Submission from {ctx.author.mention}: {link}"
        if tags:
            content += "  " + " ".join(f"#{t}" for t in tag_list)
        sent = await voting_chan.send(content)
    else:
        return await ctx.send("❌ Please provide a link or attach a file to submit.")
    # Add voting reactions
    await sent.add_reaction("👍")
    await sent.add_reaction("👎")

    if attachments:
        c.execute(
            "INSERT INTO audio_submissions (user_id, filename, timestamp, orig_message_id, tags, message_id) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, attachments[0].filename, now_iso, ctx.message.id, tags, sent.id),
        )
    else:
        c.execute(
            "INSERT INTO link_submissions (user_id, link, timestamp, tags, orig_message_id, message_id) VALUES (?, ?, ?, ?, ?, ?)",
            (uid, link, now_iso, tags, ctx.message.id, sent.id),
        )
    conn.commit()

    await ctx.send(
        f"✅ Submission posted in {voting_chan.mention}. Voting is now open."
    )

    # --- Streak update: one submission per day increments streak ---
    user_id = str(ctx.author.id)
    today = datetime.now(timezone.utc).date().isoformat()
    c.execute(
        "SELECT current, best, last_date FROM streaks WHERE user_id = ?", (user_id,)
    )
    row = c.fetchone()
    if row:
        current, best, last_date = row
        if last_date != today:
            last_dt = datetime.fromisoformat(last_date).date() if last_date else None
            if last_dt and (datetime.now(timezone.utc).date() - last_dt).days == 1:
                current += 1
            else:
                current = 1
            best = max(best, current)
            c.execute(
                "UPDATE streaks SET current = ?, best = ?, last_date = ? WHERE user_id = ?",
                (current, best, today, user_id),
            )
    else:
        current, best = 1, 1
        c.execute(
            "INSERT INTO streaks(user_id, current, best, last_date) VALUES(?,?,?,?)",
            (user_id, current, best, today),
        )
    conn.commit()

@bot.command()
async def rank(ctx):
    user_id = str(ctx.author.id)
    result = c.execute("SELECT points FROM rankings WHERE user_id = ?", (user_id,)).fetchone()
    points = result[0] if result else 0
    await ctx.send(f"📊 {ctx.author.mention}, you have **{points}** points.")

@bot.command()
async def leaderboard(ctx):
    """Show the top 5 creators by points."""
    # Exclude the bot user from the public leaderboard
    bot_id = str(bot.user.id)
    c.execute(
        "SELECT user_id, points FROM rankings WHERE user_id != ? "
        "ORDER BY points DESC LIMIT 5",
        (bot_id,)
    )
    top = c.fetchall()
    if not top:
        return await ctx.send("🏆 No submissions yet; no leaderboard available.")
    text = "🏆 **Top 5 Creators:**\n" + "\n".join(
        [f"{i+1}. <@{user}> – {pts} pts" for i, (user, pts) in enumerate(top)]
    )
    await ctx.send(text)

@bot.command(name='vote')
async def vote(ctx, score: int = None):
    """Cast a graded (1–10) vote by replying to a submission message."""
    if score is None or not 1 <= score <= 10:
        return await ctx.send("❌ Usage: reply to a submission and do `!vote <1-10>`." )
    ref = ctx.message.reference
    if not ref or not ref.message_id:
        return await ctx.send("❌ Please reply to a submission message to cast your vote.")
    msg_id = ref.message_id
    # Lookup submission timestamp: allow submissions or forwarded messages
    c.execute("SELECT timestamp FROM messages WHERE message_id = ?", (msg_id,))
    row = c.fetchone()
    if not row:
        c.execute(
            "SELECT timestamp FROM audio_submissions WHERE message_id = ?", (msg_id,)
        )
        row = c.fetchone()
    if not row:
        c.execute(
            "SELECT timestamp FROM link_submissions WHERE message_id = ?", (msg_id,)
        )
        row = c.fetchone()
    if not row:
        return await ctx.send("❌ That message is not recognized as a submission.")
    # Enforce voting window
    msg_ts = datetime.fromisoformat(row[0])
    if (datetime.now(timezone.utc) - msg_ts).total_seconds() > VOTE_WINDOW_HOURS * 3600:
        return await ctx.send("❌ Voting period has closed for that submission.")
    # Record vote (unique per user+message)
    voter_id = str(ctx.author.id)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        c.execute(
            "INSERT INTO message_votes(message_id, voter_id, score, ts) VALUES(?,?,?,?)",
            (msg_id, voter_id, score, now_iso),
        )
        conn.commit()
        await ctx.send(f"✅ Your vote of {score} has been recorded.")
    except sqlite3.IntegrityError:
        await ctx.send("❌ You have already voted on this submission.")

@bot.command()
@commands.has_permissions(administrator=True)
async def postprompt(ctx):
    """Post today's creative challenge as an embed with optional banner."""
    prompt = await get_prompt()
    embed = discord.Embed(
        title="🎯 Today's Creative Challenge",
        description=prompt,
        color=discord.Color.purple(),
    )
    banner = os.getenv('DAILY_BANNER_URL')
    if banner:
        embed.set_image(url=banner)
    await ctx.send(embed=embed)

@postprompt.error
async def postprompt_error(ctx, error):
    # Handle missing-permissions error cleanly
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permissions to use this command.")
    else:
        raise error

@bot.command(name='postrules')
@commands.has_permissions(administrator=True)
async def postrules(ctx):
    """Post the community guidelines into the rules channel."""
    try:
        with open('community_guidelines.md', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        await ctx.send("❌ community_guidelines.md file not found.")
        return
    rules_chan = bot.get_channel(RULES_CHANNEL_ID)
    if not rules_chan:
        await ctx.send("❌ Rules channel not found. Check RULES_CHANNEL_ID.")
        return
    for chunk in [content[i:i+2000] for i in range(0, len(content), 2000)]:
        await rules_chan.send(chunk)
    await ctx.send(f"✅ Community guidelines posted in {rules_chan.mention}.")

@bot.command(name='search')
async def search(ctx, tag: str = None):
    """Search past submissions by #tag."""
    if not tag:
        return await ctx.send("❌ Please specify a tag to search, e.g. `!search #music`." )
    tag_clean = tag.lstrip('#')
    results = []
    # link submissions
    c.execute(
        "SELECT user_id, link, timestamp FROM link_submissions WHERE tags LIKE ?",
        (f"%{tag_clean}%",)
    )
    for user_id, link, ts in c.fetchall():
        results.append(f"🔗 {link} by <@{user_id}> at {ts}")
    # file submissions
    c.execute(
        "SELECT user_id, filename, timestamp FROM audio_submissions WHERE tags LIKE ?",
        (f"%{tag_clean}%",)
    )
    for user_id, filename, ts in c.fetchall():
        results.append(f"📁 {filename} by <@{user_id}> at {ts}")
    if not results:
        return await ctx.send(f"🔍 No submissions found tagged #{tag_clean}.")
    # limit output
    out = results[:10]
    await ctx.send(f"🔍 Search results for #{tag_clean}:\n" + "\n".join(out))

@bot.command(name='memes')
async def memes(ctx):
    """Fetch trending meme images from Twitter and post to the memes-and-vibes channel."""
    # Only allow administrators or server managers
    perms = ctx.author.guild_permissions if ctx.guild else None
    if not perms or not (perms.administrator or perms.manage_guild):
        return await ctx.send(
            "❌ You need Administrator or Manage Server permissions to use this command."
        )
    # Scrape memes via Nitter (no JS, lightweight)
    url = (
        "https://nitter.net/search"
        "?f=images&q=%23meme"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    # Fetch meme page; wrap to handle header-size or network errors
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                html = await resp.text()
    except Exception as e:
        print(f"[❌] Meme fetch error: {e}")
        return await ctx.send(
            "⚠️ Unable to fetch memes right now. Please try again later."
        )
    soup = BeautifulSoup(html, 'html.parser')
    # Nitter attachments use <img class="attachment-image" src="/...">
    imgs = soup.find_all('img', class_='attachment-image')
    seen = set()
    memes = []
    for img in imgs:
        src = img.get('src', '')
        if not src:
            continue
        # build absolute URL
        if src.startswith('/'):
            src = 'https://nitter.net' + src
        if src.startswith('//'):
            src = 'https:' + src
        if src not in seen:
            seen.add(src)
            memes.append(src)
        if len(memes) >= 5:
            break
    if not memes:
        return await ctx.send("🔍 No memes found at the moment. Try again later.")
    channel = bot.get_channel(MEMES_CHANNEL_ID)
    for src in memes:
        if channel:
            await channel.send(src)
    await ctx.send("✅ Posted latest memes!")

@bot.command(name='scrape')
@commands.is_owner()
async def scrape(ctx):
    """(Owner-only) Scrape trending and funny memes from Twitter via Nitter fallback and post to the memes-and-vibes channel."""
    headers = {"User-Agent": "Mozilla/5.0"}
    memes = []
    # Track seen URLs to avoid duplicates across sources
    seen = set()
    async with aiohttp.ClientSession() as session:
        # Try Nitter instances first for Twitter-sourced memes
        for base in NITTER_INSTANCES:
            try:
                fetch_url = f"{base}/search?f=images&q=%23meme%20OR%23funny%20OR%23trending"
                async with session.get(fetch_url, headers=headers) as resp:
                    if resp.status != 200:
                        continue
                    html = await resp.text()
            except Exception:
                continue

            soup = BeautifulSoup(html, "html.parser")
            for img in soup.find_all("img", class_="attachment-image"):
                src = img.get("src", "")
                if not src:
                    continue
                if src.startswith("/"):
                    src = base + src
                if src.startswith("//"):
                    src = "https:" + src
                if src not in seen:
                    seen.add(src)
                    memes.append(src)
                if len(memes) >= SCRAPE_LIMIT:
                    break
            if memes:
                break

        # Fallback to Reddit r/memes top posts if no Twitter memes found
        if not memes:
            try:
                reddit_url = f"https://www.reddit.com/r/memes/top/.json?limit={SCRAPE_LIMIT}&t=day"
                async with session.get(reddit_url, headers=headers) as rresp:
                    if rresp.status == 200:
                        data = await rresp.json()
                        for child in data.get("data", {}).get("children", []):
                            url = child.get("data", {}).get("url_overridden_by_dest") or child.get("data", {}).get("url")
                            if url and any(url.lower().endswith(ext) for ext in (".jpg", ".png", ".gif")) and url not in seen:
                                seen.add(url)
                                memes.append(url)
                            if len(memes) >= SCRAPE_LIMIT:
                                break
            except Exception:
                pass

    if not memes:
        return await ctx.send("🔍 No memes found at the moment. Try again later.")

    channel = bot.get_channel(MEMES_CHANNEL_ID)
    if not channel:
        return await ctx.send("❌ Memes channel not found. Check configuration.")
    for src in memes:
        await channel.send(src)
    await ctx.send("✅ Scraped and posted latest memes!")

@scrape.error
async def scrape_error(ctx, error):
    """Handle permission errors for the scrape command."""
    if isinstance(error, commands.NotOwner):
        await ctx.send("❌ Only the bot owner can use this command.")
    else:
        raise error

@bot.command(name='music')
async def music(ctx, type: str = 'track', *, query: str = None):
    """
    Search Spotify for tracks, albums, or artists.

    Usage: !music [track|album|artist] <search terms>
    """
    if not query:
        return await ctx.send("❌ Please provide search terms. Usage: !music [track|album|artist] <search terms>")

    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        return await ctx.send(
            "❌ Please configure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in environment."
        )

    # Client Credentials flow
    token_url = 'https://accounts.spotify.com/api/token'
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            token_url,
            data={'grant_type': 'client_credentials'},
            headers={'Authorization': f'Basic {auth_header}'},
        )
        data = await resp.json()
        if resp.status != 200 or 'access_token' not in data:
            return await ctx.send(f"❌ Token error {resp.status}: {data}")

        token = data['access_token']
        headers = {'Authorization': f'Bearer {token}'}
        params = {'q': query, 'type': type, 'limit': 5}
        search_url = 'https://api.spotify.com/v1/search'
        resp2 = await session.get(search_url, headers=headers, params=params)
        results = await resp2.json()
        if resp2.status != 200:
            return await ctx.send(f"❌ Spotify API error {resp2.status}: {results}")

    items = results.get(f"{type}s", {}).get('items', [])
    if not items:
        return await ctx.send("🔍 No results found.")

    lines = []
    for item in items:
        if type == 'track':
            name = item.get('name')
            artists = ', '.join(a['name'] for a in item.get('artists', []))
            url = item.get('external_urls', {}).get('spotify')
            lines.append(f"{name} by {artists} - {url}")
        elif type == 'album':
            name = item.get('name')
            artists = ', '.join(a['name'] for a in item.get('artists', []))
            url = item.get('external_urls', {}).get('spotify')
            lines.append(f"{name} by {artists} - {url}")
        elif type == 'artist':
            name = item.get('name')
            genres = ', '.join(item.get('genres', []))
            url = item.get('external_urls', {}).get('spotify')
            lines.append(f"{name} (Genres: {genres}) - {url}")
    await ctx.send("\n".join(lines))

@bot.command(name='chat')
async def chat(ctx, *, prompt: str = None):
    """Chat with the AI assistant. Usage: `!chat your question here`"""
    if not prompt:
        return await ctx.send("❌ Please provide a message for the AI, e.g. `!chat Hello! How are you?`")
    # Ensure the OpenAI key is configured
    if not os.getenv('OPENAI_API_KEY'):
        print("[AI DEBUG] Missing OPENAI_API_KEY")
        return await ctx.send("❌ OPENAI_API_KEY not configured; chat is unavailable.")
    # Debug: log the outgoing prompt
    print(f"[AI DEBUG] Prompt: {prompt}")
    try:
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.7,
        )
        reply = resp.choices[0].message.content.strip()
        await ctx.send(reply)
        print(f"[AI DEBUG] Reply: {reply}")
    except OpenAIError as e:
        err_msg = str(e)
        await ctx.send(f"⚠️ AI request failed: {err_msg}")
        print(f"[AI ERROR] OpenAIError: {err_msg}")
    except Exception as e:
        await ctx.send(f"⚠️ Unexpected error during AI request: {e}")
        print(f"[AI ERROR] {e}")


# Giphy search command
@bot.command(name='gif')
async def gif(ctx, *, query: str = None):
    """Search Giphy for a GIF. Usage: !gif <search terms>"""
    if not query:
        return await ctx.send("❌ Please provide search terms. Usage: !gif <search terms>")
    api_key = os.getenv('GIPHY_API_KEY')
    if not api_key:
        return await ctx.send("❌ GIPHY_API_KEY not configured.")
    url = 'https://api.giphy.com/v1/gifs/search'
    params = {'api_key': api_key, 'q': query, 'limit': 5, 'rating': 'pg'}
    async with aiohttp.ClientSession() as session:
        resp = await session.get(url, params=params)
        if resp.status != 200:
            text = await resp.text()
            return await ctx.send(f"❌ Giphy API error {resp.status}: {text}")
        data = await resp.json()
    results = data.get('data', [])
    if not results:
        return await ctx.send(f"🔍 No GIFs found for '{query}'.")
    gif_item = random.choice(results)
    gif_url = gif_item.get('images', {}).get('original', {}).get('url')
    if not gif_url:
        return await ctx.send("⚠️ Couldn't parse GIF URL from response.")
    await ctx.send(gif_url)

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
        # Add vote reactions (thumbs-up/thumbs-down) to the original message for attachments
        await message.add_reaction("👍")
        await message.add_reaction("👎")
        print(f"📸 Passive submission by {message.author} | MsgID: {message.id}")
        att = message.attachments[0]
        now_iso = datetime.now(timezone.utc).isoformat()
        # Record submission metadata (tags + original message for reply-votes)
        tag_list = [w.lstrip('#') for w in message.content.split() if w.startswith('#')]
        tags = ' '.join(tag_list)
        c.execute(
            "INSERT INTO audio_submissions (user_id, filename, timestamp, orig_message_id, tags) VALUES (?, ?, ?, ?, ?)",
            (uid, att.filename, now_iso, message.id, tags)
        )
        sub_id = c.lastrowid
        conn.commit()
        # Award 1 submission point
        c.execute(
            "INSERT OR REPLACE INTO rankings (user_id, points) VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + ?)",
            (uid, uid, 1)
        )
        conn.commit()
        # Post; no immediate points, voting only
        chan = bot.get_channel(VOTING_HALL_CHANNEL_ID)
        content = f"📥 **File Submission from {message.author.mention}:**"
        if tags:
            content += "  " + " ".join(f"#{t}" for t in tag_list)
        sent = await chan.send(content, file=await att.to_file())
        # Pre-add voting reactions for neutral starting point
        await sent.add_reaction("👍")
        await sent.add_reaction("👎")
        # Only record message ID for voting
        c.execute(
            "UPDATE audio_submissions SET message_id = ? WHERE id = ?",
            (sent.id, sub_id)
        )
        conn.commit()
    await chan.send("✅ Submission accepted! Voting is now open.")

    # Link submission (record tags + original message)
    raw = message.content.strip()
    if raw:
        now_iso = datetime.now(timezone.utc).isoformat()
        words = raw.split()
        # extract tags (e.g. #tag)
        tag_list = [w.lstrip('#') for w in words if w.startswith('#')]
        tags = ' '.join(tag_list)
        # determine body: if first word is a URL, treat as link; otherwise use full text minus tags
        first = words[0]
        if first.startswith(('http://', 'https://')):
            body = first
        else:
            body = ' '.join(w for w in words if not w.startswith('#'))
        # record submission
        c.execute(
            "INSERT INTO link_submissions (user_id, link, timestamp, tags, orig_message_id) VALUES (?, ?, ?, ?, ?)",
            (uid, body, now_iso, tags, message.id)
        )
        sub_id = c.lastrowid
        conn.commit()
        # Award 1 submission point
        c.execute(
            "INSERT OR REPLACE INTO rankings (user_id, points) VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + ?)",
            (uid, uid, 1)
        )
        conn.commit()
        chan = bot.get_channel(VOTING_HALL_CHANNEL_ID)
        # post full body text
        content = f"📥 **Link Submission from {message.author.mention}:** {body}"
        if tags:
            content += "  " + " ".join(f"#{t}" for t in tag_list)
        sent = await chan.send(content)
        # Pre-add voting reactions for neutral starting point
        await sent.add_reaction("👍")
        await sent.add_reaction("👎")
        # record message ID for voting
        c.execute(
            "UPDATE link_submissions SET message_id = ? WHERE id = ?",
            (sent.id, sub_id)
        )
        conn.commit()
        # Confirm submission; voting via reactions only
        await chan.send("✅ Submission accepted! Voting is now open.")

# Run bot
@bot.event
async def on_command_error(ctx, error):
    """Silence unknown commands instead of logging exceptions."""
    if isinstance(error, commands.CommandNotFound):
        return
    raise error

with trace("LoopBot"):
    bot.run(TOKEN)
