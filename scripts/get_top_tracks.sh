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

# Obtain Spotify access token via Client Credentials flow
if [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
  echo "❌ CLIENT_ID and CLIENT_SECRET must be set in .env"
  exit 1
fi
TOKEN=$(curl -s -X POST https://accounts.spotify.com/api/token \
  -H "Authorization: Basic $(echo -n "$CLIENT_ID:$CLIENT_SECRET" | base64)" \
  -d grant_type=client_credentials \
  | jq -r .access_token)
if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "❌ Failed to obtain Spotify access token"
  exit 1
fi

# Determine market and find the Top Hits US playlist dynamically
MARKET="${1:-US}"
# Query the Top Lists category to get the playlist ID for this market
cat_resp=$(curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.spotify.com/v1/browse/categories/toplists/playlists?country=${MARKET}&limit=1")
# Extract playlist ID; fallback to known Top Hits US ID if not present
PL_ID=$(echo "$cat_resp" | jq -r '.playlists.items[0].id')
if [[ -z "$PL_ID" || "$PL_ID" == "null" ]]; then
  echo "⚠️ Toplists category lookup failed for market $MARKET; falling back to global US Top Hits"
  PL_ID="${SPOTIFY_TOP_HITS_PLAYLIST:-37i9dQZF1DXcBWIGoYBM5M}"
fi

# Fetch top 5 tracks for the playlist
curl -s \
  -H "Authorization: Bearer $TOKEN" \
  "https://api.spotify.com/v1/playlists/${PL_ID}/tracks?limit=5" \
| jq .
