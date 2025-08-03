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
3. The `Procfile` tells Railway to start LoopBot as a background worker.
4. In the Railway dashboard, add your environment variables:
   - `DISCORD_BOT_TOKEN` (required)
   - `OPENAI_API_KEY` (required for AI prompts)
   - (Optional) `RUN_SCHEDULE`, `DAILY_BANNER_URL`, etc.
5. **Persisting the SQLite database:**
   - Railway containers are ephemeral, so mount a Persistent Volume at `/data`.
   - In the Railway Dashboard, add a Volume and mount it to `/data`.
   - The bot auto-detects `RAILWAY_PERSISTENT_DIR` (or `DATA_DIR`) for `rankings.db`.
     Your DB file will live at `/data/rankings.db` and survive restarts.
   - **Restoring a backup:** If you have an existing `rankings.db` locally, commit it to your repo
     at the project root before deploying. On first run, the bot will copy that file into
     the volume so your previous points and leaderboard are preserved.
   - **Important:** The bot now requires either a mounted volume at `/data` or an explicit `DB_PATH` env var.
     It will exit with an error if neither is provided.
5. Deploy – LoopBot will stay online continuously.
