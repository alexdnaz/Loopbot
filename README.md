# LoopBot
# Changelog

## Version 1.1

- Support native Discord attachments for submissions (all file types).
- Fallback search for recent attachments when not replying or providing a link.
- Passive and `!submit` flows now add vote reactions (⬆️/⬇️) and auto-thread submissions.
- Store original message IDs (`orig_message_id`) to enable reply-based `!vote` on both user and bot messages.
- Added `!postrules` admin command to publish community guidelines from `community_guidelines.md`.

## Deployment on Railway.app

To keep LoopBot running 24/7 on Railway's free tier, you can use the included `Procfile`:

```
worker: python bot.py
```

Steps:
1. Create a new service on Railway and connect your GitHub repository.
2. Railway will detect the included `Dockerfile` and build using it.
4. In the Railway dashboard, add your environment variables:
   - `DISCORD_BOT_TOKEN` (required)
   - `OPENAI_API_KEY` (required for AI prompts)
   - `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` (required for `!music` command)
   - `SPOTIFY_MARKET` (required; a 2-letter country code, e.g. `US`, to fetch that market's Top 10)
   - **Prerequisite:** `jq` must be installed in your environment (or Docker image) for helper script JSON parsing
   - (Optional) `RUN_SCHEDULE`, `DAILY_BANNER_URL`, etc.
5. **Persisting the SQLite database:**
   - Railway containers are ephemeral, so mount a Persistent Volume at `/data`.
   - In the Railway Dashboard, add a Volume and set its **Mount Path** to `/data`.
   - LoopBot now auto-detects `/data` (or `RAILWAY_PERSISTENT_DIR`/`DATA_DIR`) to store `rankings.db`.
     Your DB file will live at `/data/rankings.db` and survive restarts.
   - **Restoring a backup:** If you have an existing `rankings.db` locally, commit it to your repo
     at the project root before deploying. On first run, the bot will copy that file into
     the volume so your previous points and leaderboard are preserved.
   - **Important:** The bot now requires one of:
     1. A mounted volume at `/data` (via `RAILWAY_PERSISTENT_DIR`/`DATA_DIR`).
     2. An explicit `DB_PATH` env var pointing to a writable path.
     3. A committed `rankings.db` at the repo root (for ephemeral fallback).
     If none are available, the bot will exit with an error.
5. Deploy – LoopBot will stay online continuously.

## Crypto price tracker
LoopBot can now post Bitcoin, Ethereum, and Solana prices on a schedule.
- To enable: set a volume or `DB_PATH` as above and redeploy.
- Posts go to channel ID `1401992445251817472` on the hour, every hour by default.
- To adjust interval (in hours), set `CRYPTO_INTERVAL_HOURS` in your env.

## Spotify OAuth & Redirect URI Requirements

Spotify now enforces stricter redirect URI validation as of November 2:

- **HTTPS is required** for all redirect URIs, **except** when using a loopback address.
- For loopback URIs, use the explicit IPv4 or IPv6 form:
  - `http://127.0.0.1:<PORT>`
  - `http://[::1]:<PORT>`
- The hostname `localhost` is **not** allowed as a redirect URI.

Be sure to register your redirect URIs accordingly in the Spotify Developer Dashboard under your app settings.

**Tip:** The bot now directly fetches the official Top Hits US playlist for a consistent Top 10 (override via `SPOTIFY_TOP_HITS_PLAYLIST`).
   Optionally, you can pass a market code (`!music <market>`) or set `SPOTIFY_MARKET` to annotate results, but the playlist itself remains the US Top Hits chart; the helper always requests without a market filter to avoid errors.

**Note:** The `!music` command uses Spotify's Client Credentials flow, which only supports read‑access to **public** playlists. Private or collaborative playlists will not be accessible and will result in empty track lists.

## Automated Invite Emailer

You can auto-generate and send personalized Discord invite emails by using the provided `invite_automation.py` script, which calls the OpenAI API to draft email content and then sends messages via SMTP.

### Prerequisites

- Python 3.7+
- `openai` Python package (`pip install openai`)

### Setup

1. **Prepare your recipients list** by creating `recipients.csv` in the project root with headers `name,email`, for example:

   ```csv
   name,email
   Alice,alice@example.com
   Bob,bob@example.com
   ```

2. **Provision OpenAI & email credentials** by adding them to your local `.env` (git‑ignored):

   ```dotenv
   # OpenAI
   OPENAI_API_KEY=sk-...your-key...

   # SparkPost SMTP (example)
   SMTP_HOST=smtp.sparkpostmail.com
   SMTP_PORT=587
   SMTP_USER=SMTP_Injection
   SMTP_PASS=YOUR_SPARKPOST_API_KEY
   EMAIL_FROM="Your Name <you@yourdomain.com>"

   # Discord invite
   INVITE_LINK=https://discord.gg/yourcode
   SERVER_NAME="LoopBot Creators’ Hub"

   # (Optional) override default email subject
   EMAIL_SUBJECT="Join LoopBot Creators’ Hub!"
   ```

3. **Install** the OpenAI client and dotenv loader:

   ```bash
   pip install openai python-dotenv
   ```

### Usage of Invite Automation

Run the script to generate & send invites:

```bash
python invite_automation.py
```

Every entry in `recipients.csv` will receive a personalized invite email (via SparkPost SMTP).

### Opt-In Double-Confirmation Web Form

You can also collect *opt-in* subscribers via a simple web subscription form powered by Flask.

1. Install Flask:

   ```bash
   pip install flask
   ```

2. Ensure your SMTP and invite settings are set (same env vars used by `invite_automation.py`), plus:

   | Variable   | Description                            |
   |------------|----------------------------------------|
   | `BASE_URL` | Public URL where `optin.py` is served  |

3. Run the opt-in app:

   ```bash
   python optin.py
   ```

4. Point users at `BASE_URL/`, have them submit name & email, then click the emailed confirmation link.
   Confirmed addresses are appended to `recipients.csv`, users receive your Discord invite,
   and can download the free lead‑magnet PDF.

### Lead Magnet PDF

Place your free guide (the “lead magnet”) as `lead_magnet.pdf` in the `static/` directory:

```
static/lead_magnet.pdf
```

After a user confirms, the download link `BASE_URL/static/lead_magnet.pdf` is included in the invite email.
