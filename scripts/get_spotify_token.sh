#!/usr/bin/env bash
# Retrieve a Spotify API access token via the Client Credentials flow.

# Ensure CLIENT_ID and CLIENT_SECRET are set
if [[ -z "$CLIENT_ID" || -z "$CLIENT_SECRET" ]]; then
  echo "❌ CLIENT_ID and CLIENT_SECRET environment variables must be set."
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
