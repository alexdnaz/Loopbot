#!/usr/bin/env python3
"""
generate_secret_key.py

Generate a URL-safe random secret key for Flask applications.
Usage:
    python generate_secret_key.py
Outputs a 32-byte secret suitable for setting as SECRET_KEY.
"""
import secrets

def main():
    # 32 bytes URL-safe token (~43 characters)
    print(secrets.token_urlsafe(32))

if __name__ == "__main__":
    main()
