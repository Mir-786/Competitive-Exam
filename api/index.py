import os
import uuid
from typing import List, Optional, Dict
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Coaching LMS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Admin credentials
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin@apex2026")
ADMIN_SESSION_TOKEN = "session-admin-auth-token-xyz"

# In-memory storage (Replace with Supabase/PostgreSQL/MongoDB for serverless persistence)
DB: Dict = {
    "users": [
        {"username": "student", "password": "password123", "name": "Rahul Verma", "email": "rahul@example.com", "role": "student"}
    ],
    "classes": [
        {
            "id": "c1",
            "title": "Indian Polity: Fundamental Rights Crash Course",
            "subject": "General Studies",
            "video_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
            "duration": "45 Mins"
        }
    ],
    "quizzes": [
        {
            "id": "q1",
            "title": "Modern Indian History Mock Test",
            "subject": "History",
            "duration_minutes": 10,
            "questions": [
                {
                    "id": "q101",
                    "text": "Who was the Viceroy of India during the Partition of Bengal in 1905?",
                    "options": ["Lord Curzon", "Lord Chelmsford", "Lord Minto", "Lord Hardinge"],
                    "correct_option": 0,
                    "explanation": "Lord Curzon served as Viceroy from 1899 to 1905 and ordered the partition of Bengal."
                }
            ]
        }
    ],
    "pdfs": [
        {
            "id": "p1",
            "title": "Quantitative Aptitude: Speed Maths Formula Sheet",
            "subject": "Aptitude",
            "file_url": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
            "pages": 12
        }
    ],
    "submissions": []
}

# --- Pydantic Schemas ---
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    username: str
    password: str

class ClassCreate(BaseModel):
    title: str
    subject: str
    video_url: str
    duration: str

class PDFCreate(BaseModel):
    title: str
    subject: str
    file_url: str
    pages: int

class QuestionModel(BaseModel):
    id: Optional[str] = None
    text: str
    options: List[str]
    correct_option: int
    explanation: Optional[str] = ""

class QuizCreate(BaseModel):
    title: str
    subject: str
    duration_minutes: int
    questions: List[QuestionModel]

class QuizSubmit(BaseModel):
    quiz_id: str
    answers: Dict[str, int]

# --- Admin Dependency ---
def require_admin(authorization: Optional[str] = Header(None)):
    if not authorization or authorization != f"Bearer {ADMIN_SESSION_TOKEN}":
        raise HTTPException(status_code=403, detail="Unauthorized Admin Access")
    return True

# --- Authentication & Registration Endpoints ---

@app.post("/api/auth/register")
def register_student(req: RegisterRequest):
    clean_username = req.username.strip().lower()
    
    # Prohibit registering the admin username
    if clean_username == ADMIN_USER.lower():
        raise HTTPException(status_code=400, detail="This username is reserved. Please choose another.")
    
    # Check if username or email already exists
    if any(u["username"].lower() == clean_username for u in DB["users"]):
        raise HTTPException(status_code=400, detail="Username is already taken.")
    if any(u.get("email", "").lower() == req.email.strip().lower() for u in DB["users"]):
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    new_user = {
        "name": req.name.strip(),
        "email": req.email.strip(),
        "username": clean_username,
        "password": req.password,
        "role": "student"
    }
    DB["users"].append(new_user)

    # Automatically authenticate and return student session
    return {
        "status": "success",
        "role": "student",
        "token": f"student-token-{uuid.uuid4()}",
        "name": new_user["name"]
    }

@app.post("/api/auth/login")
def login(creds: LoginRequest):
    u = creds.username.strip()
    p = creds.password

    # 1. Admin Verification
    if u == ADMIN_USER and p == ADMIN_PASS:
        return {
            "status": "success",
            "role": "admin",
            "token": ADMIN_SESSION_TOKEN,
            "name": "System Administrator"
        }

    # 2. Student Verification
    user = next((item for item in DB["users"] if item["username"].lower() == u.lower() and item["password"] == p), None)
    if user:
        return {
            "status": "success",
            "role": "student",
            "token": f"student-token-{uuid.uuid4()}",
            "name": user["name"]
        }

    raise HTTPException(status_code=401, detail="Invalid username or password.")

# --- Content Routes ---

@app.get("/api/classes")
def get_classes():
    return {"classes": DB["classes"]}

@app.post("/api/admin/classes")
def add_class(item: ClassCreate, auth: bool = Depends(require_admin)):
    new_class = item.model_dump()
    new_class["id"] = "c-" + str(uuid.uuid4())[:6]
    DB["classes"].append(new_class)
    return {"message": "Class added", "item": new_class}

@app.delete("/api/admin/classes/{cid}")
def delete_class(cid: str, auth: bool = Depends(require_admin)):
    DB["classes"] = [c for c in DB["classes"] if c["id"] != cid]
    return {"message": "Class deleted"}

@app.get("/api/pdfs")
def get_pdfs():
    return {"pdfs": DB["pdfs"]}

@app.post("/api/admin/pdfs")
def add_pdf(item: PDFCreate, auth: bool = Depends(require_admin)):
    new_pdf = item.model_dump()
    new_pdf["id"] = "p-" + str(uuid.uuid4())[:6]
    DB["pdfs"].append(new_pdf)
    return {"message": "PDF added", "item": new_pdf}

@app.delete("/api/admin/pdfs/{pid}")
def delete_pdf(pid: str, auth: bool = Depends(require_admin)):
    DB["pdfs"] = [p for p in DB["pdfs"] if p["id"] != pid]
    return {"message": "PDF removed"}

@app.get("/api/quizzes")
def get_quizzes():
    return {
        "quizzes": [
            {
                "id": q["id"],
                "title": q["title"],
                "subject": q["subject"],
                "duration_minutes": q["duration_minutes"],
                "total_questions": len(q["questions"])
            }
            for q in DB["quizzes"]
        ]
    }

@app.get("/api/quizzes/{quiz_id}")
def get_quiz_questions(quiz_id: str):
    quiz = next((q for q in DB["quizzes"] if q["id"] == quiz_id), None)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    clean_questions = [
        {"id": q["id"], "text": q["text"], "options": q["options"]}
        for q in quiz["questions"]
    ]
    return {
        "id": quiz["id"],
        "title": quiz["title"],
        "duration_minutes": quiz["duration_minutes"],
        "questions": clean_questions
    }

@app.post("/api/quizzes/submit")
def submit_quiz(sub: QuizSubmit):
    quiz = next((q for q in DB["quizzes"] if q["id"] == sub.quiz_id), None)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    score = 0
    results = []
    for q in quiz["questions"]:
        qid = q["id"]
        selected = sub.answers.get(qid, -1)
        is_correct = (selected == q["correct_option"])
        if is_correct:
            score += 1
        results.append({
            "question": q["text"],
            "options": q["options"],
            "selected": selected,
            "correct": q["correct_option"],
            "is_correct": is_correct,
            "explanation": q.get("explanation", "")
        })

    return {
        "score": score,
        "total": len(quiz["questions"]),
        "percentage": round((score / len(quiz["questions"])) * 100, 1),
        "results": results
    }

@app.post("/api/admin/quizzes")
def create_quiz(quiz: QuizCreate, auth: bool = Depends(require_admin)):
    new_quiz = quiz.model_dump()
    new_quiz["id"] = "q-" + str(uuid.uuid4())[:6]
    for idx, qu in enumerate(new_quiz["questions"]):
        if not qu.get("id"):
            qu["id"] = f"q-{idx+1}"
    DB["quizzes"].append(new_quiz)
    return {"message": "Quiz created successfully", "quiz": new_quiz}

# UI Root
@app.get("/", response_class=HTMLResponse)
def index_view():
    index_path = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Coaching Platform Running</h1>"
