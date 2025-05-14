### FILE: app.py

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import os
import json
import datetime
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from pywebpush import webpush, WebPushException

app = Flask(__name__)
app.secret_key = "super_secret_key"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

DATA_FILE = "data/tasks.json"
SUBSCRIPTIONS_FILE = "data/subscriptions.json"

# Static VAPID keys
vapid_keys = {
    'publicKey': 'BOupU8wr20bcCcEfgmq7xuKDn5tnRI06Ex17U5nkWJCeJ7cCxyfSln2uWGr6u7LJv6MrNZVvo3rw79D0s3sGhV8=',
    'privateKey': 'YZb47VZB25RinP80KxV0qJCO7P_4FLGTTI0z_oI3BNs=',
    'vapid_email': 'mailto:you@example.com'
}

# Create data folder if missing
os.makedirs("data", exist_ok=True)

def load_tasks():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(DATA_FILE, "w") as f:
        json.dump(tasks, f, indent=4)

def load_subscriptions():
    if os.path.exists(SUBSCRIPTIONS_FILE):
        with open(SUBSCRIPTIONS_FILE, "r") as f:
            return json.load(f)
    return []

def save_subscriptions(subs):
    with open(SUBSCRIPTIONS_FILE, "w") as f:
        json.dump(subs, f, indent=4)

def send_push_to_all(title):
    subs = load_subscriptions()
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=title,
                vapid_private_key=vapid_keys['privateKey'],
                vapid_claims={"sub": vapid_keys['vapid_email']}
            )
        except WebPushException as e:
            print(f"[ERROR] Failed to send push: {e}")

@app.route("/")
def index():
    tasks = load_tasks()
    return render_template("index.html", tasks=tasks, vapid_pub_key=vapid_keys['publicKey'])

@app.route("/add-task", methods=["POST"])
def add_task():
    tasks = load_tasks()
    task = {
        "name": request.form["name"],
        "priority": request.form["priority"],
        "duration": request.form["duration"],
        "energy": request.form["energy"],
        "deadline": request.form["deadline"],
        "start_time": request.form["start_time"]
    }
    tasks.append(task)
    save_tasks(tasks)
    send_push_to_all(f"Task added: {task['name']}")
    return redirect(url_for("index"))

@app.route("/remove-task/<int:task_index>", methods=["POST"])
def remove_task(task_index):
    tasks = load_tasks()
    if 0 <= task_index < len(tasks):
        task = tasks.pop(task_index)
        save_tasks(tasks)
        send_push_to_all(f"Task removed: {task['name']}")
    return redirect(url_for("index"))

@app.route("/subscribe", methods=["POST"])
def subscribe():
    subscription = request.get_json()
    subs = load_subscriptions()
    if subscription not in subs:
        subs.append(subscription)
        save_subscriptions(subs)
    return jsonify({"status": "subscribed"}), 201

@app.route("/service-worker.js")
def service_worker():
    return send_from_directory("static", "service-worker.js")

@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/calendar", "openid", "https://www.googleapis.com/auth/userinfo.email"],
        redirect_uri="http://localhost:8080/oauth2callback"
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true', prompt='consent')
    session["state"] = state
    return redirect(authorization_url)

@app.route("/oauth2callback")
def oauth2callback():
    if "state" not in session:
        return redirect(url_for("authorize"))

    state = session["state"]
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/calendar", "openid", "https://www.googleapis.com/auth/userinfo.email"],
        state=state,
        redirect_uri="http://localhost:8080/oauth2callback"
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }
    return redirect(url_for("schedule"))

@app.route("/schedule")
def schedule():
    if "credentials" not in session:
        return redirect(url_for("authorize"))

    creds = google.oauth2.credentials.Credentials(**session["credentials"])
    user_info_service = build("oauth2", "v2", credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    user_email = user_info.get("email", "Unknown")

    calendar_service = build("calendar", "v3", credentials=creds)
    tasks = load_tasks()
    added_events = []

    for task in tasks:
        try:
            task_name = task["name"]
            duration_minutes = int(task["duration"])
            deadline_date = task["deadline"]
            start_time_str = task.get("start_time", "10:00")
            start_dt = datetime.datetime.strptime(f"{deadline_date} {start_time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

            event = {
                'summary': task_name,
                'description': f"Priority: {task['priority']}, Energy: {task['energy']}",
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
                'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'}
            }

            created_event = calendar_service.events().insert(calendarId='primary', body=event).execute()
            added_events.append({"name": task_name, "link": created_event.get('htmlLink')})
        except Exception as e:
            print(f"[ERROR] Could not add {task['name']}: {e}")

    return render_template("authenticated.html", email=user_email, events=added_events)

if __name__ == "__main__":
    app.run(debug=True, port=8080)