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
4. In the Railway dashboard, add your environment variables (e.g. `DISCORD_BOT_TOKEN`, `OPENAI_API_KEY`, etc.).
5. Deploy – LoopBot will stay online continuously.
