#!/usr/bin/env bash
# Unified Spotify helper script: client-token, user-token, list-categories, top-tracks

set -euo pipefail

# Ensure jq is installed
if ! command -v jq &>/dev/null; then
  echo "❌ 'jq' is required but not found. Please install jq in your environment or include it in your Docker image." >&2
  exit 1
fi
# Load environment variables from project root .env if present
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
  echo "🔍 Loading environment from $ENV_FILE" >&2
  set -o allexport; source "$ENV_FILE"; set +o allexport
fi

# Auto-load saved tokens if present
if [[ -z "${SPOTIFY_USER_TOKEN:-}" && -f "$PROJECT_ROOT/user_token.txt" ]]; then
  SPOTIFY_USER_TOKEN=$(<"$PROJECT_ROOT/user_token.txt")
  export SPOTIFY_USER_TOKEN
fi
if [[ -z "${SPOTIFY_CLIENT_TOKEN:-}" && -f "$PROJECT_ROOT/client_token.txt" ]]; then
  SPOTIFY_CLIENT_TOKEN=$(<"$PROJECT_ROOT/client_token.txt")
  export SPOTIFY_CLIENT_TOKEN
fi

usage() {
  cat <<USAGE
Usage: $(basename "$0") <command> [args]

Commands:
  client-token                Acquire and cache a client-credentials access token
  user-token                  Run PKCE flow to get & cache a user access token (auto-opens browser)
  list-categories [limit]     List Spotify browse categories (default limit=5)
  top-tracks [time_range] [n] Fetch your Top N personal tracks (default n=50); time_range: short_term|medium_term|long_term
  charts [region] [n]     Fetch Top N tracks from Spotify official Top 50 charts (region, default GLOBAL)
  help                        Show this help message
USAGE
  exit 1
}

get_client_token() {
  # Support SPOTIFY_CLIENT_ID/SECRET or CLIENT_ID/SECRET
  cid=${SPOTIFY_CLIENT_ID:-${CLIENT_ID:-}}
  secret=${SPOTIFY_CLIENT_SECRET:-${CLIENT_SECRET:-}}
  if [[ -z "$cid" || -z "$secret" ]]; then
    echo "❌ SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET (or CLIENT_ID/CLIENT_SECRET) must be set" >&2
    exit 1
  fi
  token=$(curl -s -X POST https://accounts.spotify.com/api/token \
    -H "Authorization: Basic $(echo -n "$cid:$secret" | base64)" \
    -d grant_type=client_credentials \
    | jq -r .access_token)
  # persist for reuse
  echo "$token" > "$PROJECT_ROOT/client_token.txt"
  echo "$token"
}

get_user_token() {
  if [[ -z "${CLIENT_ID:-}" || -z "${REDIRECT_URI:-}" ]]; then
    echo "❌ CLIENT_ID and REDIRECT_URI must be set" >&2
    exit 1
  fi
  # PKCE parameters
  CODE_VERIFIER=$(head -c128 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c64)
  CODE_CHALLENGE=$(printf '%s' "$CODE_VERIFIER" \
    | openssl dgst -sha256 -binary \
    | openssl base64 \
    | tr '+/' '-_' \
    | tr -d '=')

SCOPES="playlist-read-private%20playlist-read-collaborative%20user-top-read"
  AUTH_URL="https://accounts.spotify.com/authorize?client_id=$CLIENT_ID&response_type=code&redirect_uri=$REDIRECT_URI&scope=$SCOPES&code_challenge_method=S256&code_challenge=$CODE_CHALLENGE"
  echo "👉 Open this URL in your browser to authorize:" >&2
  echo "  $AUTH_URL" >&2
  if command -v xdg-open &>/dev/null; then xdg-open "$AUTH_URL" &>/dev/null || true; fi
  if command -v open &>/dev/null; then open "$AUTH_URL" &>/dev/null || true; fi

  AUTH_CODE=$(python3 - <<PYCODE
import http.server, socketserver, urllib.parse, sys
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        code = urllib.parse.parse_qs(qs).get('code',[''])[0]
        print(code)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Authorized, you may close this tab.")
        sys.exit(0)
port = urllib.parse.urlparse("$REDIRECT_URI").port
with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
    httpd.handle_request()
PYCODE
)
  resp=$(curl -s -X POST https://accounts.spotify.com/api/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d grant_type=authorization_code \
    -d code="$AUTH_CODE" \
    -d redirect_uri="$REDIRECT_URI" \
    -d client_id="$CLIENT_ID" \
    --data-urlencode "code_verifier=$CODE_VERIFIER")
  token=$(echo "$resp" | jq -r .access_token)
  if [[ -z "$token" || "$token" == "null" ]]; then
    echo "❌ Failed to retrieve user token:" >&2
    echo "$resp" | jq .error >&2
    exit 1
  fi
  echo "$token" > "$PROJECT_ROOT/user_token.txt"
  echo "✅ User token saved to $PROJECT_ROOT/user_token.txt" >&2
}

list_categories() {
  limit=${1:-5}
  # Use user token if available, else fallback to client credentials
  if [[ -n "${SPOTIFY_USER_TOKEN:-}" ]]; then
    token="$SPOTIFY_USER_TOKEN"
  else
    if [[ -z "${SPOTIFY_CLIENT_TOKEN:-}" ]]; then
      echo "🔐 Generating client token for public categories..." >&2
      token=$(get_client_token)
      SPOTIFY_CLIENT_TOKEN="$token"
      export SPOTIFY_CLIENT_TOKEN
    else
      token="$SPOTIFY_CLIENT_TOKEN"
    fi
  fi
  curl -s -H "Authorization: Bearer $token" \
    "https://api.spotify.com/v1/browse/categories?country=${SPOTIFY_MARKET:-US}&limit=$limit" \
    | jq -r '.categories.items[] | "- \(.id): \(.name)"'
}

### Fetch Top 5 tracks helper
fetch_tracks() {
  local tok=$1 url
  # Omit market filter to avoid empty results due to regional availability
  url="https://api.spotify.com/v1/playlists/${pl_id}/tracks?limit=5"
  local resp body code
  resp=$(curl -s -H "Authorization: Bearer $tok" "$url" -w "\n%{http_code}")
  body=$(echo "$resp" | sed '$d')
  code=$(echo "$resp" | tail -n1)
  if [[ "$code" -ne 200 ]]; then
    echo "$body" | jq . >&2
    echo "🔗 Request URL: $url" >&2
    return $code
  fi
  echo "$body" | jq -r '.items[] | "- \(.track.name) by \(.track.artists|map(.name)|join(", "))"'
}

### Retrieve user's top tracks (time_range=short_term, medium_term, or long_term)
top_tracks() {
  local time_range=${1:-short_term}
  local limit=${2:-50}
  # Ensure we have a user token (generate via PKCE if needed)
  if [[ -z "${SPOTIFY_USER_TOKEN:-}" ]]; then
    echo "🔐 No user token found; invoking OAuth flow to get one..." >&2
    get_user_token
    if [[ ! -s "$PROJECT_ROOT/user_token.txt" ]]; then
      echo "❌ User-token flow failed; please complete authorization in the browser." >&2
      exit 1
    fi
    SPOTIFY_USER_TOKEN=$(<"$PROJECT_ROOT/user_token.txt")
    export SPOTIFY_USER_TOKEN
  fi
  # Fetch user's top tracks and check for errors or empty result
  # Fetch user's top tracks with auto-refresh on insufficient scopes
  resp=$(curl -s -H "Authorization: Bearer $SPOTIFY_USER_TOKEN" \
    "https://api.spotify.com/v1/me/top/tracks?time_range=${time_range}&limit=${limit}" \
    -w "\n%{http_code}")
  body=$(echo "$resp" | sed '$d')
  code=$(echo "$resp" | tail -n1)
  if [[ "$code" -ne 200 ]]; then
    # If token lacks user-top-read, re-run OAuth to refresh
    if [[ "$code" -eq 403 || "$code" -eq 401 ]]; then
      echo "🔐 User token scope may be insufficient; refreshing via OAuth flow..." >&2
      get_user_token
      if [[ ! -s "$PROJECT_ROOT/user_token.txt" ]]; then
        echo "❌ Failed to refresh user token; aborting." >&2
        exit 1
      fi
      SPOTIFY_USER_TOKEN=$(<"$PROJECT_ROOT/user_token.txt")
      export SPOTIFY_USER_TOKEN
      # retry
      resp=$(curl -s -H "Authorization: Bearer $SPOTIFY_USER_TOKEN" \
        "https://api.spotify.com/v1/me/top/tracks?time_range=${time_range}&limit=${limit}" \
        -w "\n%{http_code}")
      body=$(echo "$resp" | sed '$d')
      code=$(echo "$resp" | tail -n1)
      if [[ "$code" -ne 200 ]]; then
        echo "$body" | jq . >&2
        exit $code
      fi
    else
      echo "$body" | jq . >&2
      echo "🔗 Request URL: https://api.spotify.com/v1/me/top/tracks?time_range=${time_range}&limit=${limit}" >&2
      exit $code
    fi
  fi
  if ! echo "$body" | jq -e '.items and (.items|length>0)' >/dev/null; then
    echo "⚠️ No top-tracks data returned. Ensure you have listening history and proper scopes (user-top-read)." >&2
    exit 1
  fi
  echo "$body" | jq -r '.items[] | "- \(.name) by \(.artists|map(.name)|join(", "))"'
}

### Fetch Top 50 regional charts (Global, US, etc.) from Official Spotify Top 50
charts() {
  local region=${1:-GLOBAL}
  local region_uc
  region_uc=$(echo "$region" | tr '[:lower:]' '[:upper:]')
  local limit=${2:-5}
  echo "🔍 Searching for official Top 50 ${region_uc} playlist" >&2
  # Always use fresh client credentials token for public charts
  token=$(get_client_token)
  if [[ -z "$token" || "$token" == "null" ]]; then
    echo "❌ Failed to obtain Spotify client token; ensure CLIENT_ID/SECRET or SPOTIFY_CLIENT_ID/SECRET are set" >&2
    exit 1
  fi
  # Try search queries for region (e.g. US -> USA, United States)
  declare -a search_terms
  search_terms=("${region_uc}")
  if [[ "$region_uc" == "US" ]]; then
    search_terms+=("USA" "United%20States")
  fi
  pl_id=""
  for t in "${search_terms[@]}"; do
    echo "🔍 Searching for Top 50 $t playlist" >&2
    pl_id=$(curl -s -H "Authorization: Bearer $token" \
      "https://api.spotify.com/v1/search?q=Top%2050%20${t}&type=playlist&limit=10" \
      | jq -r --arg R "$region_uc" '[.playlists.items[]? | select(.name? and (.name|test("Top 50";"i"))) | select(.name|test($R;"i"))][0].id')
    if [[ -n "$pl_id" && "$pl_id" != "null" ]]; then
      break
    fi
  done
  if [[ -z "$pl_id" || "$pl_id" == "null" ]]; then
    if [[ "$region_uc" == "US" ]]; then
      # Fallback to static official US Top Hits playlist
      pl_id="${SPOTIFY_TOP_HITS_PLAYLIST:-37i9dQZF1DXcBWIGoYBM5M}"
      echo "⚠️ Falling back to static US Top Hits playlist: $pl_id" >&2
    else
      echo "❌ Could not find the official Top 50 ${region_uc} playlist via search." >&2
      exit 1
    fi
  fi
  echo "🔗 Fetching Top ${limit} tracks from playlist $pl_id" >&2
  # Directly fetch playlist tracks with given limit
  resp=$(curl -s -H "Authorization: Bearer $token" \
    "https://api.spotify.com/v1/playlists/${pl_id}/tracks?limit=${limit}" \
    -w "\n%{http_code}")
  body=$(echo "$resp" | sed '$d')
  code=$(echo "$resp" | tail -n1)
  if [[ "$code" -ne 200 ]]; then
    echo "$body" | jq . >&2
    echo "🔗 Request URL: https://api.spotify.com/v1/playlists/${pl_id}/tracks?limit=${limit}" >&2
    exit $code
  fi
  echo "$body" | jq -r '.items[] | "- \(.track.name) by \(.track.artists|map(.name)|join(", "))"'
}

if (( $# < 1 )); then usage; fi
cmd=$1; shift
case "$cmd" in
  client-token) get_client_token ;;
  user-token) get_user_token ;;
  list-categories) list_categories "$@" ;;
  top-tracks) top_tracks "$@" ;;
  charts) charts "$@" ;;
  help|--help|-h) usage ;;
  *) echo "❌ Unknown command: $cmd" >&2; usage ;;
esac
