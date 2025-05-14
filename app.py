### FILE: app.py

from ml import optimize_tasks
from flask import Flask, render_template, request, redirect, url_for, session
import os
import json
import datetime
import google.oauth2.credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

app = Flask(__name__)
app.secret_key = "super_secret_key"  # Change this in production
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # For testing only

DATA_FILE = "data/tasks.json"

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

@app.route("/")
def index():
    tasks = load_tasks()
    return render_template("index.html", tasks=tasks)

@app.route("/add-task", methods=["POST"])
def add_task():
    tasks = load_tasks()
    task = {
        "name": request.form["name"],
        "priority": request.form["priority"],
        "duration": request.form["duration"],
        "energy": request.form["energy"],
        "deadline": request.form["deadline"],
    }
    tasks.append(task)
    save_tasks(tasks)
    return redirect(url_for("index"))

@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/calendar.readonly", "openid", "https://www.googleapis.com/auth/userinfo.email"],
        redirect_uri="http://localhost:8080/oauth2callback"
    )
    authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
    session["state"] = state
    return redirect(authorization_url)

@app.route("/oauth2callback")
def oauth2callback():
    if "state" not in session:
        return redirect(url_for("authorize"))  # fallback if user skips authorize

    state = session["state"]
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/calendar.readonly", "openid", "https://www.googleapis.com/auth/userinfo.email"],
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

    # Get user email
    user_info_service = build("oauth2", "v2", credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    user_email = user_info.get("email", "Unknown")
    print(f"[INFO] Authenticated user email: {user_email}")

    # Simulate sending token to user's email (print to console)
    print(f"[MOCK EMAIL] Sending token to {user_email}: {creds.token}")

    # Print Google Calendar events to console
    calendar_service = build("calendar", "v3", credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    events_result = calendar_service.events().list(
        calendarId="primary", timeMin=now,
        maxResults=5, singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])
    if not events:
        print("[INFO] No upcoming events found.")
    else:
        print("[INFO] Upcoming Google Calendar events:")
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            print(f"{start} - {event.get('summary', 'No Title')}")

    return render_template("authenticated.html", email=user_email)

if __name__ == "__main__":
    app.run(debug=True, port=8080)
