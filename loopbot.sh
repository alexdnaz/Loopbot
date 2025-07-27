#!/usr/bin/env bash

# Ensure we're in the script directory and activate the virtualenv
cd "$(dirname "$0")"
source bin/activate

echo "🔁 Starting Discord bot loop..."

while true; do
    echo "🚀 Launching bot.py..."
    python bot.py

    echo "💥 Bot crashed or exited. Restarting in 5 seconds..."
    sleep 5
done
