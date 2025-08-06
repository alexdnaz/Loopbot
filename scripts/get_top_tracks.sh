#!/usr/bin/env bash
# Retrieve Top 5 tracks from the official Spotify Top Hits US playlist (or override via env).

# Determine script and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables (CLIENT_ID/SECRET, optional SPOTIFY_TOP_HITS_PLAYLIST)
ENV_FILE="$PROJECT_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
elif [[ -f "$PWD/.env" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "$PWD/.env"
  set +o allexport
fi

# Ensure helper exists
: "${SCRIPT_DIR}/get_spotify_token.sh" || { echo "Helper not found"; exit 1; }

# Fetch access token
TOKEN=$(bash "$SCRIPT_DIR/get_spotify_token.sh" | awk '/^Got token:/ {print $3}')

# Determine playlist and market
PL_ID="${SPOTIFY_TOP_HITS_PLAYLIST:-37i9dQZF1DXcBWIGoYBM5M}"
MARKET="${1:-US}"

# Fetch top tracks via Spotify API (omit market filter for public US playlist)
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.spotify.com/v1/playlists/${PL_ID}/tracks?limit=5" \
| jq .
