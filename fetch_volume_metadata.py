#!/usr/bin/env python3
"""
fetch_volume_metadata.py

Fetch Railway volume metadata (ID, name, mount path) via Railway's GraphQL Public API.
Reads RAILWAY_API_KEY, PROJECT_ID, SERVICE_ID from a local .env file.
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('RAILWAY_API_KEY')
PROJECT_ID = os.getenv('RAILWAY_PROJECT_ID')
SERVICE_ID = os.getenv('RAILWAY_SERVICE_ID')

if not API_KEY or not PROJECT_ID or not SERVICE_ID:
    print("Missing one of RAILWAY_API_KEY, PROJECT_ID, or SERVICE_ID in .env", file=sys.stderr)
    sys.exit(1)

url = 'https://railway.app/graphql'
headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}
query = '''
query GetVolumes($projectId: ID!, $serviceId: ID!) {
  project(id: $projectId) {
    service(id: $serviceId) {
      config {
        volumes {
          id
          name
          mountPath
        }
      }
    }
  }
}
'''
variables = {
    'projectId': PROJECT_ID,
    'serviceId': SERVICE_ID
}

resp = requests.post(url, headers=headers, json={'query': query, 'variables': variables})
if resp.status_code != 200:
    print(f'Error: HTTP {resp.status_code} - {resp.text}', file=sys.stderr)
    sys.exit(1)

data = resp.json()
errors = data.get('errors')
if errors:
    print('GraphQL errors:', file=sys.stderr)
    for err in errors:
        print(err.get('message'), file=sys.stderr)
    sys.exit(1)

volumes = data['data']['project']['service']['config']['volumes'] or []
if not volumes:
    print('No volumes found.')
    sys.exit(0)

print('Volumes metadata:')
for vol in volumes:
    print(f"- ID: {vol['id']}, Name: {vol['name']}, MountPath: {vol['mountPath']}")
