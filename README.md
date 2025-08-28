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
  
   - **Optional tracing control:** `OPENAI_AGENTS_DISABLE_TRACING=1` to disable built-in OpenAI Agents tracing
  
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

## Railway SSH & File Transfer

Railway SSH differs significantly from traditional SSH implementations. Understanding how it works helps explain its capabilities and limitations.

Railway SSH does not use the standard SSH protocol (sshd). Instead, it establishes connections via a custom protocol built on top of websockets.

This approach provides several advantages:

- No need to configure SSH daemons in your containers.
- Secure communication through Railway's existing authentication.
- Works with any container that has a shell available.

This approach is secure by design:

- No SSH daemon exposed publicly on your containers.
- All communication goes through Railway's authenticated infrastructure.
- Services remain isolated from direct internet access.
- Uses Railway's existing security and access control mechanisms.

Limitations and Workarounds

Understanding Railway SSH's limitations helps you plan appropriate workflows and implement effective workarounds for tasks that aren't directly supported.

#### File Transfer Limitations

Railway SSH does not support traditional file transfer methods:

- No SCP (Secure Copy Protocol) support for copying files between local and remote systems.
- No sFTP (SSH File Transfer Protocol) functionality for file management.
- No direct file download/upload capabilities through the SSH connection.

#### File transfer workarounds

**Connect volume to file explorer service:** Deploy a simple file browser service that mounts the same volume as your main application. This provides web-based access to your files for download and upload operations.

**Use CURL for file uploads:** From within the SSH session, upload files to external services:

```bash
# Upload file to a temporary file sharing service
curl -X POST -F "file=@database_dump.sql" https://file.io/

# Upload to cloud storage (example with AWS S3)
aws s3 cp database_dump.sql s3://your-bucket/backups/

# Upload via HTTP to your own endpoint
curl -X POST -F "file=@logfile.txt" https://your-app.com/admin/upload
```

## Crypto price tracker
LoopBot can now post Bitcoin, Ethereum, and Solana prices on a schedule.
- To enable: set a volume or `DB_PATH` as above and redeploy.
- Posts go to channel ID `1401992445251817472` on the hour, every hour by default.
- To adjust interval (in hours), set `CRYPTO_INTERVAL_HOURS` in your env.
- To customize tracked coins, set `CRYPTO_TICKERS` to a comma-separated list of CoinGecko coin IDs (default: `bitcoin,ethereum,solana`).

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
   pip install openai python-dotenv openai-agents
   ```

### Usage of Invite Automation

Run the script to generate & send invites. Tracing is enabled by default so you can monitor runs in the
[OpenAI Traces dashboard](https://platform.openai.com/traces). To disable tracing for a single run:

```bash
export OPENAI_AGENTS_DISABLE_TRACING=1
```

```bash
python invite_automation.py
```

Every entry in `recipients.csv` will receive a personalized invite email.

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

4. After submitting your details, you’ll be redirected to a thank‑you page instructing you to check your email for a confirmation link.
   Once you click that link, you’ll receive a Discord invite **and** the lead‑magnet PDF as an email attachment.

### Lead Magnet PDF

Place your free guide (the “lead magnet”) as `lead_magnet.pdf` in the `static/` directory:

```
static/lead_magnet.pdf
```

After a user confirms, the download link `BASE_URL/static/lead_magnet.pdf` is included in the invite email.

## Fetch Volume Metadata via GraphQL

You can retrieve your Railway volume configuration (ID, name, mount path) using the Public GraphQL API and our helper script.

1. Option A: If you have a **Project Access Token**, fetch your Project and Environment IDs via GraphQL:
   ```bash
   pip install python-dotenv requests
   python fetch_project_env.py
   ```
   Copy the printed `PROJECT_ID` and `ENVIRONMENT_ID` into your `.env` for step 2.

2. Add your credentials and identifiers to `.env`:
   ```dotenv
   RAILWAY_API_KEY=sk-...
   RAILWAY_PROJECT_ID=<your-project-id>
   RAILWAY_SERVICE_ID=<your-service-id>
   ```

2. Install dependencies (GraphQL helper uses `requests` and `python-dotenv`):
   ```bash
   pip install python-dotenv requests
   ```

3. Run the script to list your volumes (will call https://railway.app/graphql):
   ```bash
   python fetch_volume_metadata.py
   ```

This will output all volumes attached to your Loopbot service along with their mount paths.

## Fetch Volume Metadata via GraphQL

You can retrieve your Railway volume configuration (ID, name, mount path) using the Public GraphQL API and our helper script.

1. Add your credentials and identifiers to `.env`:
   ```dotenv
   RAILWAY_API_KEY=sk-...
   RAILWAY_PROJECT_ID=<your-project-id>
   RAILWAY_SERVICE_ID=<your-service-id>
   ```

2. Install dependencies (GraphQL helper uses `requests` and `python-dotenv`):
   ```bash
   pip install python-dotenv requests
   ```

3. Run the script to list your volumes:
   ```bash
   python fetch_volume_metadata.py
   ```

This will output all volumes attached to your Loopbot service along with their mount paths.
