#!/usr/bin/env bash

# Ensure we're in the script directory and activate the virtualenv
cd "$(dirname "$0")"
source bin/activate

# Redirect all output (stdout/stderr) to discord.log
exec >> discord.log 2>&1

echo "🔁 Starting Discord bot loop (caffeinated)..."

# Prevent system sleep while the bot is running
caffeinate -dimsu &
CAFFEINATE_PID=$!
trap "echo '🛑 Stopping caffeinate'; kill $CAFFEINATE_PID" EXIT

while true; do
    echo "🚀 Launching bot.py..."
    # Use python3 to ensure correct interpreter
    python3 bot.py

    echo "💥 Bot crashed or exited. Restarting in 5 seconds..."
    sleep 5
done
