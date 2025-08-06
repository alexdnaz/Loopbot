#!/usr/bin/env bash
# Retrieve a Spotify API access token via the Client Credentials flow.

# Load environment variables from .env in project root if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
# Load from project-root .env or fallback to cwd .env
if [[ -f "$ENV_FILE" ]]; then
  echo "🔍 Loading environment from $ENV_FILE"
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
elif [[ -f "$PWD/.env" ]]; then
  echo "🔍 Loading environment from $PWD/.env"
  set -o allexport
  # shellcheck disable=SC1090
  source "$PWD/.env"
  set +o allexport
fi
# Ensure CLIENT_ID and CLIENT_SECRET are set
if [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
  echo "❌ CLIENT_ID and CLIENT_SECRET environment variables must be set (or defined in .env)."
  exit 1
fi

# Request a token
TOKEN=$(curl -s -X POST https://accounts.spotify.com/api/token \
  -H "Authorization: Basic $(echo -n "$CLIENT_ID:$CLIENT_SECRET" | base64)" \
  -d grant_type=client_credentials \
  | jq -r .access_token)

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "❌ Failed to retrieve access token."
  exit 1
fi

echo "Got token: $TOKEN"
