#!/usr/bin/env python3
"""
optin.py

A simple Flask app to collect email opt-ins with double opt-in confirmation.
Subscribers are added to recipients.csv upon confirmation.
"""

import os
import uuid
import sqlite3
import smtplib
from datetime import datetime
from email.message import EmailMessage
from flask import Flask, request, redirect, url_for, render_template_string, flash

# Configuration from environment
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
EMAIL_FROM = os.getenv('EMAIL_FROM')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
INVITE_LINK = os.getenv('INVITE_LINK', '')
SERVER_NAME = os.getenv('SERVER_NAME', 'Discord Server')

if not all([SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_FROM, INVITE_LINK]):
    raise RuntimeError('SMTP_HOST, SMTP_USER, SMTP_PASS, EMAIL_FROM, and INVITE_LINK must be set')

# Setup DB for pending tokens
conn = sqlite3.connect('optin.db', check_same_thread=False)
cur = conn.cursor()
cur.execute(
    'CREATE TABLE IF NOT EXISTS pending (token TEXT PRIMARY KEY, name TEXT, email TEXT, created TIMESTAMP)'
)
conn.commit()

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(16))

SUBSCRIBE_FORM = '''
<!doctype html>
<title>Get Your Free Guide & Join Our Discord</title>
{% with messages = get_flashed_messages() %}
  {% if messages %}<ul>{% for m in messages %}<li>{{m}}</li>{% endfor %}</ul>{% endif %}
{% endwith %}
<h2>Claim Your Free Guide to LoopBot + Community Invite</h2>
<p>Enter your name and email below to receive our free PDF guide on mastering LoopBot, plus an invite to our Discord server.</p>
<form method=post>
  <label>Name: <input type=text name=name required></label><br>
  <label>Email: <input type=email name=email required></label><br>
  <input type=submit value='Send Me the Guide & Invite'>
</form>
'''

@app.route('/', methods=['GET', 'POST'])
def subscribe():
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip().lower()
        token = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        cur.execute('INSERT INTO pending(token,name,email,created) VALUES (?,?,?,?)', (token, name, email, now))
        conn.commit()
        send_confirmation(email, name, token)
        flash('Confirmation email sent. Please check your inbox.')
        return redirect(url_for('subscribe'))
    return render_template_string(SUBSCRIBE_FORM)

@app.route('/confirm/<token>')
def confirm(token):
    cur.execute('SELECT name,email FROM pending WHERE token=?', (token,))
    row = cur.fetchone()
    if not row:
        return '<h3>Invalid or expired token.</h3>', 400
    name, email = row
    # append to CSV if not exists
    csv_path = 'recipients.csv'
    seen = set()
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            for line in f:
                parts = line.strip().split(',', 1)
                if len(parts) == 2:
                    seen.add(parts[1].lower())
    if email not in seen:
        with open(csv_path, 'a') as f:
            f.write(f'{name},{email}\n')
    # send the actual invite link
    try:
        send_invite(name, email)
    except Exception:
        pass
    # cleanup pending token
    cur.execute('DELETE FROM pending WHERE token=?', (token,))
    conn.commit()
    return f'<h3>Thank you {name}! A Discord invite has been sent to {email}.</h3>'

def send_confirmation(email, name, token):
    confirm_url = f"{BASE_URL}{url_for('confirm', token=token)}"
    subject = f"Confirm your subscription to our Discord"
    body = (
        f"Hi {name},\n\n"
        "Thanks for subscribing to join our Discord community!\n"
        f"Please confirm your email address by clicking the link below:\n{confirm_url}\n\n"
        "Once confirmed, we’ll send you the invite link.\n\n"
        "If you didn’t request this, you can ignore this message.\n"
    )
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = email
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

def send_invite(name, email):
    """Send the Discord invite link after confirmation."""
    subject = f"Your invite to {SERVER_NAME} on Discord"
    body = (
        f"Hi {name},\n\n"
        "Thanks for confirming your subscription!\n\n"
        f"Here’s your invite link to join {SERVER_NAME}:\n{INVITE_LINK}\n\n"
        f"You can also download your free guide here: {BASE_URL}/static/lead_magnet.pdf\n\n"
        "See you inside!\n"
    )
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = email
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

if __name__ == '__main__':
    # preload CSV header if missing
    if not os.path.exists('recipients.csv'):
        with open('recipients.csv', 'w') as f:
            f.write('name,email\n')
    app.run(host='0.0.0.0', port=5000)
