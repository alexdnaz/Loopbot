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
# Voting summary schedule (default shortly after leaderboard)
# Voting summary schedule (default one hour before leaderboard)
VOTE_SUMMARY_HOUR = int(os.getenv(
    'VOTE_SUMMARY_HOUR', str((LEADERBOARD_HOUR - 1) % 24)
))
VOTE_SUMMARY_MINUTE = int(os.getenv('VOTE_SUMMARY_MINUTE', str(LEADERBOARD_MINUTE)))

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
# Ensure submissions tables have tags field for tag-based search
try:
    c.execute('ALTER TABLE audio_submissions ADD COLUMN tags TEXT')
    c.execute('ALTER TABLE link_submissions ADD COLUMN tags TEXT')
    conn.commit()
except sqlite3.OperationalError:
    pass

# Tables for storing submissions and votes
c.execute('''CREATE TABLE IF NOT EXISTS audio_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    filename TEXT,
    timestamp TEXT,
    thread_id INTEGER,
    message_id INTEGER
)''')
c.execute('''CREATE TABLE IF NOT EXISTS link_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    link TEXT,
    timestamp TEXT,
    tags TEXT,
    thread_id INTEGER,
    message_id INTEGER
)''')
c.execute('''CREATE TABLE IF NOT EXISTS votes (
    user_id TEXT,
    submission_id INTEGER,
    score INTEGER,
    PRIMARY KEY(user_id, submission_id)
)''')
conn.commit()
# Add original message ID columns if missing (for reply-based voting)
try:
    c.execute('ALTER TABLE audio_submissions ADD COLUMN orig_message_id INTEGER')
    c.execute('ALTER TABLE link_submissions ADD COLUMN orig_message_id INTEGER')
    conn.commit()
except sqlite3.OperationalError:
    pass

# Tables for storing submissions and votes
c.execute('''CREATE TABLE IF NOT EXISTS audio_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    filename TEXT,
    timestamp TEXT,
    thread_id INTEGER,
    message_id INTEGER
)''')
c.execute('''CREATE TABLE IF NOT EXISTS link_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    link TEXT,
    timestamp TEXT,
    tags TEXT,
    thread_id INTEGER,
    message_id INTEGER
)''')
c.execute('''CREATE TABLE IF NOT EXISTS votes (
    user_id TEXT,
    submission_id INTEGER,
    score INTEGER,
    PRIMARY KEY(user_id, submission_id)
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

@tasks.loop(time=dtime(hour=LEADERBOARD_HOUR, minute=LEADERBOARD_MINUTE))
async def post_daily_leaderboard():
    """Post the daily top-5 leaderboard at the configured time."""
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if channel:
        c.execute(
            "SELECT user_id, points FROM rankings ORDER BY points DESC LIMIT 5"
        )
        top = c.fetchall()
        if top:
            embed = discord.Embed(
                title="🏆 Top 5 Creators",
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

@tasks.loop(time=dtime(hour=VOTE_SUMMARY_HOUR, minute=VOTE_SUMMARY_MINUTE))
async def post_vote_summary():
    """Post a daily summary of top-voted submissions in the voting-hall channel."""
    channel = bot.get_channel(VOTING_HALL_CHANNEL_ID)
    if channel:
        c.execute(
            "SELECT submission_id, SUM(score) AS total FROM votes "
            "GROUP BY submission_id ORDER BY total DESC LIMIT 5"
        )
        rows = c.fetchall()
        if not rows:
            await channel.send("🏅 No votes have been cast yet.")
            return
        embed = discord.Embed(
            title="🏅 Top 5 Voted Submissions",
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
                value=f"Total: {total} pts",
                inline=False,
            )
        # Optional: add a thumbnail or footer
        # embed.set_thumbnail(url=channel.guild.icon_url)
        await channel.send(embed=embed)
    else:
        print("⚠️ Voting hall channel not found. Check VOTING_HALL_CHANNEL_ID.")

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
        "2. Create your work and submit it with `!submit <link>` or attach a file (audio/image/video/other).\n"
        "3. Earn 1 point per submission and bonus points for 👍 reactions.\n"
        "4. View your score with `!rank` and the top creators with `!leaderboard`.\n"
        "5. Administrators can manually post a prompt using `!postprompt`.\n"
        "6. Use `!ping` to check if I'm alive!"
    )
    await ctx.send(how_text)

@bot.command()
async def submit(ctx, link: str = None):
    """Accept a URL or an attached file (audio/image/video/other) as a submission and award points."""
    # If user replied to a message, use that message's attachment or text
    ref = ctx.message.reference
    if ref and ref.message_id:
        ref_chan = bot.get_channel(ref.channel_id) or ctx.channel
        ref_msg = await ref_chan.fetch_message(ref.message_id)
        # Only allow submitting your own messages
        if ref_msg.author.id != ctx.author.id:
            await ctx.send("❌ You can only submit your own attachments or messages.")
            return
        attachments = ref_msg.attachments
        link = None if attachments else ref_msg.content.strip()
    else:
        attachments = ctx.message.attachments
    # If no attachment/reply/link, try to find recent self-posted attachments as fallback
    if not attachments and link is None and not (ref and ref.message_id):
        async for prev in ctx.channel.history(limit=10, before=ctx.message):
            if prev.author == ctx.author and prev.attachments:
                attachments = prev.attachments
                # Keep ref for consistency (logs/threads)
                ref = prev.reference or ctx.message.reference
                break
    # Attachment path: accept any file (audio/image/video/etc.)
    if attachments:
        # React to the user's attachment message for voting
        await ctx.message.add_reaction("⬆️")
        await ctx.message.add_reaction("⬇️")
        print(f"📸 Submission by {ctx.author} | MsgID: {ctx.message.id}")
        att = attachments[0]
        now_iso = datetime.utcnow().isoformat()
        # extract tags from command content
        tag_list = [w.lstrip('#') for w in ctx.message.content.split() if w.startswith('#')]
        tags = ' '.join(tag_list)
        # record submission (tags + orig message for reply-votes)
        c.execute(
            "INSERT INTO audio_submissions (user_id, filename, timestamp, orig_message_id, tags) VALUES (?, ?, ?, ?, ?)",
            (str(ctx.author.id), att.filename, now_iso, ctx.message.id, tags)
        )
        sub_id = c.lastrowid
        conn.commit()
        # award point
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
            sent = await sub_ch.send(f"📥 **File Submission from {ctx.author.mention}:**", file=await att.to_file())
        # Skip auto-creating threads; only record message ID for voting
        c.execute(
            "UPDATE audio_submissions SET message_id = ? WHERE id = ?",
            (sent.id, sub_id)
        )
        conn.commit()
        await ctx.send(f"✅ Audio submission accepted! You now have {points} points.")
        return
    # URL submission path
    if not link:
        await ctx.send("❌ Please provide a link or attach a file.")
        return
    now_iso = datetime.utcnow().isoformat()
    c.execute(
        "INSERT INTO link_submissions (user_id, link, timestamp, tags, orig_message_id) VALUES (?, ?, ?, ?, ?)",
        (
            str(ctx.author.id),
            link,
            now_iso,
            ' '.join([w.lstrip('#') for w in ctx.message.content.split()[1:] if w.startswith('#')]),
            ctx.message.id,
        )
    )
    sub_id = c.lastrowid
    conn.commit()
    # award point
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
        sent = await sub_ch.send(f"📥 **Link Submission from {ctx.author.mention}:** {link}")
        # Skip auto-creating threads; only record message ID for voting
        c.execute(
            "UPDATE link_submissions SET message_id = ? WHERE id = ?",
            (sent.id, sub_id)
        )
        conn.commit()
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
    # Allow voting by replying to the original submission message
    sub = None
    ref = ctx.message.reference
    if ref and ref.message_id:
        # lookup submission by bot repost message or original message
        c.execute(
            "SELECT id FROM link_submissions WHERE message_id = ? OR orig_message_id = ?",
            (ref.message_id, ref.message_id)
        )
        row = c.fetchone()
        if row:
            sub = ('link', row[0])
        else:
            c.execute(
                "SELECT id FROM audio_submissions WHERE message_id = ? OR orig_message_id = ?",
                (ref.message_id, ref.message_id)
            )
            row = c.fetchone()
            if row:
                sub = ('audio', row[0])
    if not sub:
        # fallback: ensure we are in the submission thread
        thread = ctx.channel
        if hasattr(thread, 'parent_id') and thread.parent_id:
            c.execute("SELECT id FROM link_submissions WHERE thread_id = ?", (thread.id,))
            row = c.fetchone()
            sub = ('link', row[0]) if row else None
            if not sub:
                c.execute("SELECT id FROM audio_submissions WHERE thread_id = ?", (thread.id,))
                row = c.fetchone()
                sub = ('audio', row[0]) if row else None
    if not sub:
        await ctx.send("❌ You can only vote by replying to a submission or inside its thread.")
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
        # Add vote reactions to the original message for attachments
        await message.add_reaction("⬆️")
        await message.add_reaction("⬇️")
        print(f"📸 Passive submission by {message.author} | MsgID: {message.id}")
        att = message.attachments[0]
        # Record submission metadata (tags + original message for reply-votes)
        now_iso = datetime.utcnow().isoformat()
        # extract hashtags from content
        tag_list = [w.lstrip('#') for w in message.content.split() if w.startswith('#')]
        tags = ' '.join(tag_list)
        c.execute(
            "INSERT INTO audio_submissions (user_id, filename, timestamp, orig_message_id, tags) VALUES (?, ?, ?, ?, ?)",
            (uid, att.filename, now_iso, message.id, tags)
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
        c.execute(
            "UPDATE audio_submissions SET thread_id = ?, message_id = ? WHERE id = ?",
            (thread.id, sent.id, sub_id)
        )
        conn.commit()
        await chan.send(f"✅ Submission accepted! You now have {points} points.")
        return

    # Link submission (record tags + original message)
    raw = message.content.strip()
    if raw:
        now_iso = datetime.utcnow().isoformat()
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
        c.execute(
            "UPDATE link_submissions SET thread_id = ?, message_id = ? WHERE id = ?",
            (thread.id, sent.id, sub_id)
        )
        conn.commit()
        await chan.send(f"✅ Submission accepted! You now have {points} points.")

# Run bot
bot.run(TOKEN)
