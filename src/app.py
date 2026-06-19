"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import hashlib
import hmac
import json
import secrets
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

TEACHERS_FILE = current_dir / "teachers.json"
PASSWORD_ITERATIONS = 120_000
SESSION_COOKIE = "teacher_session"

app.state.sessions = {}

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


def hash_password(password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return derived.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), expected_hash)


def save_teacher_store(teachers):
    with TEACHERS_FILE.open("w", encoding="utf-8") as file:
        json.dump(teachers, file, indent=2)
        file.write("\n")


def ensure_teacher_store():
    if TEACHERS_FILE.exists():
        return

    salt = secrets.token_hex(16)
    default_teachers = [
        {
            "username": "teacher@mergington.edu",
            "salt": salt,
            "password_hash": hash_password("TeachMHS123!", salt),
        }
    ]
    save_teacher_store(default_teachers)


def load_teacher_store():
    ensure_teacher_store()
    with TEACHERS_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_teacher_by_username(username: str):
    for teacher in load_teacher_store():
        if teacher["username"] == username:
            return teacher
    return None


def get_current_teacher(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE)
    if not session_token:
        raise HTTPException(status_code=401, detail="Login required")

    username = app.state.sessions.get(session_token)
    if not username:
        raise HTTPException(status_code=401, detail="Login required")

    teacher = get_teacher_by_username(username)
    if not teacher:
        raise HTTPException(status_code=401, detail="Login required")

    return teacher


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.get("/auth/me")
def get_auth_status(request: Request):
    try:
        teacher = get_current_teacher(request)
    except HTTPException:
        return {"authenticated": False}

    return {"authenticated": True, "username": teacher["username"]}


@app.post("/auth/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")

    teacher = get_teacher_by_username(username)
    if not teacher or not verify_password(password, teacher["salt"], teacher["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_token = secrets.token_urlsafe(32)
    app.state.sessions[session_token] = username

    response = JSONResponse({"message": "Logged in successfully", "username": username})
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 8,
    )
    return response


@app.post("/auth/logout")
def logout(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token:
        app.state.sessions.pop(session_token, None)

    response = JSONResponse({"message": "Logged out successfully"})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.post("/auth/change-password")
async def change_password(request: Request, teacher=Depends(get_current_teacher)):
    body = await request.json()
    current_password = body.get("current_password", "")
    new_password = body.get("new_password", "")

    if not verify_password(current_password, teacher["salt"], teacher["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters long")

    teachers = load_teacher_store()
    for stored_teacher in teachers:
        if stored_teacher["username"] == teacher["username"]:
            new_salt = secrets.token_hex(16)
            stored_teacher["salt"] = new_salt
            stored_teacher["password_hash"] = hash_password(new_password, new_salt)
            break

    save_teacher_store(teachers)
    return {"message": "Password updated successfully"}


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, teacher=Depends(get_current_teacher)):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, teacher=Depends(get_current_teacher)):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
