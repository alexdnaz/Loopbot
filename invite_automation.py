#!/usr/bin/env python3
"""
invite_automation.py

Generate personalized Discord invite emails via OpenAI and send them via SMTP.
"""

import os
import csv
import smtplib
from email.message import EmailMessage
import openai
from agents import trace

# Configuration from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_FROM = os.getenv("EMAIL_FROM")
INVITE_LINK = os.getenv("INVITE_LINK")
SERVER_NAME = os.getenv("SERVER_NAME", "Our Discord Server")
EMAIL_SUBJECT = os.getenv("EMAIL_SUBJECT", f"Join {SERVER_NAME} on Discord!")

def check_env():
    missing = []
    for var in ("OPENAI_API_KEY", "SMTP_HOST", "SMTP_USER", "SMTP_PASS", "EMAIL_FROM", "INVITE_LINK"):  # SERVER_NAME/EMAIL_SUBJECT optional
        if not os.getenv(var):
            missing.append(var)
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

def generate_email_body(recipient_name: str) -> str:
    """Call OpenAI to draft a personalized invitation email."""
    prompt = f"""
Draft a friendly, personalized invitation email to join my Discord server.

SERVER_NAME: \"{SERVER_NAME}\"
INVITE_LINK: {INVITE_LINK}
RECIPIENT_NAME: \"{recipient_name}\"
SENDER_NAME: \"{EMAIL_FROM}\"
SELLING_POINTS:
- daily creative challenges
- built-in hashtag search
- supportive community

Please produce a full email body, using RECIPIENT_NAME in the greeting and SENDER_NAME in the sign-off.
"""
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=300,
        temperature=0.7,
    )
    return response.choices[0].text.strip()

def send_email(to_email: str, subject: str, body: str):
    """Send an email via SMTP with the given subject and body."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

def load_recipients(csv_path: str = "recipients.csv") -> list:
    """Load recipient names and emails from a CSV file with headers 'name,email'."""
    recipients = []
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row.get('name') and row.get('email'):
                recipients.append({'name': row['name'], 'email': row['email']})
    return recipients

def main():
    check_env()
    openai.api_key = OPENAI_API_KEY
    recipients = load_recipients()
    for rec in recipients:
        print(f"Generating email for {rec['name']} <{rec['email']}>...")
        body = generate_email_body(rec['name'])
        print("Sending email...")
        send_email(rec['email'], EMAIL_SUBJECT, body)
        print("Done.\n")

if __name__ == '__main__':
    # Wrap the invite workflow in a trace to collect events in the OpenAI Traces dashboard
    with trace("Invite Automation"):
        main()
