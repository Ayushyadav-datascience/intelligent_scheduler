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
        "start_time": request.form["start_time"],
    }
    tasks.append(task)
    save_tasks(tasks)
    return redirect(url_for("index"))

@app.route("/remove-task/<int:task_index>", methods=["POST"])
def remove_task(task_index):
    tasks = load_tasks()
    if 0 <= task_index < len(tasks):
        tasks.pop(task_index)
        save_tasks(tasks)
    return redirect(url_for("index"))

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

    # Get user email
    user_info_service = build("oauth2", "v2", credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    user_email = user_info.get("email", "Unknown")
    print(f"[INFO] Authenticated user email: {user_email}")

    # Build calendar service
    calendar_service = build("calendar", "v3", credentials=creds)
    tasks = load_tasks()

    added_events = []

    for task in tasks:
        try:
            task_name = task["name"]
            duration_minutes = int(task["duration"])
            deadline_date = task["deadline"]
            start_time_str = task.get("start_time", "10:00")

            # Combine date and time to full datetime
            start_dt = datetime.datetime.strptime(f"{deadline_date} {start_time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

            event = {
                'summary': task_name,
                'description': f"Priority: {task['priority']}, Energy: {task['energy']}",
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                }
            }

            created_event = calendar_service.events().insert(calendarId='primary', body=event).execute()
            event_link = created_event.get('htmlLink')
            print(f"[CALENDAR] Added task to calendar: {event_link}")
            added_events.append({"name": task_name, "link": event_link})
        except Exception as e:
            print(f"[ERROR] Failed to add task '{task_name}': {e}")

    return render_template("authenticated.html", email=user_email, events=added_events)

if __name__ == "__main__":
    app.run(debug=True, port=8080)