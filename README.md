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
1. Create a new Python service on Railway and connect your GitHub repository.
2. Railway will read `requirements.txt` and install dependencies automatically.
3. Locally, you can fetch a Spotify Client Credentials token for API calls:
   ```bash
   ./scripts/spotify.sh client-token
   ```
   Or explicitly set creds inline:
   ```bash
   CLIENT_ID=<your_spotify_client_id> \
   CLIENT_SECRET=<your_spotify_client_secret> \
     ./scripts/spotify.sh client-token
   ```
5. Show your Top N Spotify tracks (based on your listening history):
   ```bash
   ./scripts/spotify.sh top-tracks [time_range] [limit]
   ```
   - `time_range`: one of `short_term` (last 4 weeks), `medium_term` (last 6 months), or `long_term` (several years); defaults to `short_term`.
   - `limit`: number of tracks to fetch (default 50).
   - Requires a user access token (via `user-token`); the script auto-launches OAuth if missing or needs a scope refresh, and saves `user_token.txt`.

6. List the first 5 Spotify browse categories:
   ```bash
   ./scripts/spotify.sh list-categories [limit]
   ```
   This will prompt for a user token (via PKCE) if none is present.

7. The `Procfile` tells Railway to start LoopBot as a background worker.
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
  
## Generating a user-access token for `!music`

1. Ensure in your `.env` the values match exactly those registered in your Spotify App:
   ```bash
   CLIENT_ID=<your_spotify_client_id>
   REDIRECT_URI=http://127.0.0.1:8888/callback  # must use 127.0.0.1 (not 127.0.0.0 or localhost)
   ```
2. Run the helper to generate & capture a user token (auto-opens your browser & auto-captures the code):
   ```bash
   ./scripts/spotify.sh user-token
   ```
   The helper requests `playlist-read-private` and `playlist-read-collaborative` scopes for private/collab playlist access.
3. A `user_token.txt` file will be created in the project root; the `spotify.sh` script will auto-load this token for subsequent commands (e.g. `list-categories`, `top-tracks`).
