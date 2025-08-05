import os
import discord
import asyncio
import sqlite3
import itertools
import aiohttp
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, time as dtime, timezone, timedelta

import openai
import sys
import random
import re

from bs4 import BeautifulSoup

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
load_dotenv()
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
# music-share: 1393811741715988540

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
## Persistent storage detection: prefer env var, else auto‑detect mounted /data
persistent_dir = (
    os.getenv('RAILWAY_PERSISTENT_DIR')
    or os.getenv('DATA_DIR')
    or ('/data' if os.path.isdir('/data') else None)
)
# Debug: verify which directory is used for persistence
print(f"🔍 Persistent dir is: {persistent_dir}")
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
        # Trending = votes cast in the last 24 hours
        since = datetime.now(timezone.utc) - timedelta(days=1)
        threshold = since.isoformat()
        c.execute(
            "SELECT submission_id, SUM(score) AS total FROM votes "
            "WHERE timestamp >= ? GROUP BY submission_id "
            "ORDER BY total DESC LIMIT 5",
            (threshold,)
        )
        rows = c.fetchall()
        if not rows:
            await channel.send("🏅 No votes have been cast yet.")
            return
        embed = discord.Embed(
            title="📈 Trending: Top 5 in last 24h",
            color=discord.Color.green(),
        )
        for i, (sub_id, total) in enumerate(rows, start=1):
            # label from link or file
            c.execute("SELECT link FROM link_submissions WHERE id = ?", (sub_id,))
            r = c.fetchone()
            if r:
                label = r[0]
            else:
                c.execute("SELECT filename FROM audio_submissions WHERE id = ?", (sub_id,))
                ar = c.fetchone()
                label = ar[0] if ar else f"Submission #{sub_id}"
            embed.add_field(
                name=f"{i}. {label}",
                value=f"Total: {total} Votes",
                inline=False,
            )
        # Optional: add a thumbnail or footer
        # embed.set_thumbnail(url=channel.guild.icon_url)
        await channel.send(embed=embed)
    else:
        print("⚠️ Voting hall channel not found. Check VOTING_HALL_CHANNEL_ID.")


@crypto_price_tracker.before_loop
async def before_crypto_price_tracker():
    # Align first run to the next quarter-hour mark (00,15,30,45 UTC)
    await bot.wait_until_ready()
    now = datetime.now(timezone.utc)
    # seconds until next quarter
    delay = ((15 - (now.minute % 15)) * 60) - now.second
    if delay <= 0:
        delay += 15 * 60
    await asyncio.sleep(delay)

@tasks.loop(minutes=15)
async def crypto_price_tracker():
    """Fetch and post Bitcoin, Ethereum, and Solana USD prices to the crypto channel."""
    channel = bot.get_channel(CRYPTO_CHANNEL_ID)
    if not channel:
        print("⚠️ Crypto channel not found. Check CRYPTO_CHANNEL_ID.")
        return
    # Fetch top cryptocurrencies by market cap (includes images and 24h change)
    # Adjust 'per_page' to include more coins in the carousel
    per_page = int(os.getenv('CRYPTO_TOP_N', '10'))
    markets_url = (
        "https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd"
        f"&order=market_cap_desc&per_page={per_page}&page=1&sparkline=false"
    )
    async with aiohttp.ClientSession() as session:
        async with session.get(markets_url) as resp:
            data = await resp.json()
    if not data:
        print("⚠️ Failed to fetch crypto market data.")
        return
    # Send one embed per coin with its logo and 24h change (scrollable carousel)
    embeds = []
    now = datetime.now(timezone.utc)
    for coin in data:
        name = coin.get('name', '').title()
        symbol = coin.get('symbol', '').upper()
        price = coin.get('current_price')
        change24 = coin.get('price_change_percentage_24h')
        image = coin.get('image')
        embed = discord.Embed(
            title=f"{symbol} - {name}",
            color=discord.Color.dark_gold(),
            timestamp=now,
        )
        if image:
            embed.set_thumbnail(url=image)
        embed.add_field(
            name="Price (USD)",
            value=f"**${price:,}**" if price is not None else "N/A",
            inline=False,
        )
        if change24 is not None:
            arrow = "📈" if change24 >= 0 else "📉"
            embed.add_field(
                name="24h Change",
                value=f"{arrow} {change24:+.2f}%",
                inline=False,
            )
        embed.set_footer(text="Data provided by CoinGecko")
        embeds.append(embed)
    await channel.send(embeds=embeds)

# Commands
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

@bot.command(name='commands')
async def list_commands(ctx):
    await ctx.send(
        "📜 Commands: `!ping`, `!how`, `!submit <link>` or attach a file, `!vote <1-10>`, `!rank`, `!leaderboard`, `!postprompt`, `!chat <msg>`, `!search #tag`"
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

    submissions_chan = bot.get_channel(SUBMISSIONS_CHANNEL_ID)
    if not submissions_chan:
        return await ctx.send("❌ Submissions channel not found. Check configuration.")

    # Forward to submissions channel
    if attachments:
        sent = await submissions_chan.send(
            f"📥 Submission from {ctx.author.mention}",
            file=await attachments[0].to_file()
        )
    elif link:
        sent = await submissions_chan.send(
            f"📥 Submission from {ctx.author.mention}: {link}"
        )
    else:
        return await ctx.send("❌ Please provide a link or attach a file to submit.")

    await ctx.send(
        f"✅ Submission posted in {submissions_chan.mention}. Voting will open shortly."
    )

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
    """Cast a 1–10 vote for a file or link submission by replying or inside its thread."""
    if score is None:
        return await ctx.send("❌ Please provide a vote score, e.g. `!vote 7`.")
    # Identify submission by reply or thread context (audio OR link)
    sub_id = None
    ref = ctx.message.reference
    # Allow voting only on the posted submission in voting-hall (message_id)
    if ref and ref.message_id:
        for tbl in ('audio_submissions', 'link_submissions'):
            c.execute(
                f"SELECT id FROM {tbl} WHERE message_id = ?",
                (ref.message_id,)
            )
            row = c.fetchone()
            if row:
                sub_id = row[0]
                break
    # Allow voting inside a discussion thread without replying
    if not sub_id and isinstance(ctx.channel, discord.Thread):
        for tbl in ('audio_submissions', 'link_submissions'):
            c.execute(
                f"SELECT id FROM {tbl} WHERE thread_id = ?",
                (ctx.channel.id,),
            )
            row = c.fetchone()
            if row:
                sub_id = row[0]
                break
    # Fallback: allow voting in a channel context by matching the previous submission message
    if not sub_id and ctx.channel.id == VOTING_HALL_CHANNEL_ID:
        # get the most recent message before this one
        prev_msgs = [msg async for msg in ctx.channel.history(limit=1, before=ctx.message)]
        if prev_msgs:
            prev_msg = prev_msgs[0]
            for tbl in ('audio_submissions', 'link_submissions'):
                c.execute(
                    f"SELECT id FROM {tbl} WHERE message_id = ?",
                    (prev_msg.id,),
                )
                row = c.fetchone()
                if row:
                    sub_id = row[0]
                    break
    if not sub_id:
        await ctx.send(
            "❌ You can only vote by replying to the submission message in the #voting-hall."
        )
        return
    if not 1 <= score <= 10:
        return await ctx.send("❌ Please vote with a score between 1 and 10.")
    uid = str(ctx.author.id)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        c.execute(
            "INSERT INTO votes (user_id, submission_id, score, timestamp) VALUES (?, ?, ?, ?)",
            (uid, sub_id, score, now_iso),
        )
        conn.commit()
        # Award 1 point for voting
        c.execute(
            "INSERT OR REPLACE INTO rankings (user_id, points) VALUES (?, COALESCE((SELECT points FROM rankings WHERE user_id = ?), 0) + ?)",
            (uid, uid, 1),
        )
        conn.commit()
        await ctx.send(f"✅ Your vote of {score} has been recorded.")
    except sqlite3.IntegrityError:
        await ctx.send("❌ You have already voted for this submission.")

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


@bot.command(name='chat')
async def chat(ctx, *, prompt: str = None):
    """Chat with the AI assistant. Usage: `!chat your question here`"""
    if not prompt:
        return await ctx.send("❌ Please provide a message for the AI, e.g. `!chat Hello! How are you?`")
    try:
        resp = await openai.ChatCompletion.acreate(
            # Use the free tier model
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
    except Exception as e:
        await ctx.send("⚠️ AI request failed. Please try again later.")
        print(f"[AI ERROR] {e}")

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
        sent = await chan.send(f"📥 **File Submission from {message.author.mention}:**", file=await att.to_file())
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
        return

    # Link submission (record tags + original message)
    raw = message.content.strip()
    if raw:
        now_iso = datetime.now(timezone.utc).isoformat()
        parts = raw.split()
        url = parts[0]
        tag_list = [w.lstrip('#') for w in parts[1:] if w.startswith('#')]
        tags = ' '.join(tag_list)
        c.execute(
            "INSERT INTO link_submissions (user_id, link, timestamp, tags, orig_message_id) VALUES (?, ?, ?, ?, ?)",
            (uid, url, now_iso, tags, message.id)
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
        sent = await chan.send(f"📥 **Link Submission from {message.author.mention}:** {url}")
        # Pre-add voting reactions for neutral starting point
        await sent.add_reaction("👍")
        await sent.add_reaction("👎")
        # Only record message ID for voting
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

bot.run(TOKEN)
