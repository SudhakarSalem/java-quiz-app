"""
Java Quiz App
=============
FastAPI backend that:
  1. Serves a single HTML page (static/index.html) as the quiz UI.
  2. Asks a local Ollama model to generate 25 Java MCQs on demand.
  3. Grades submitted answers (4 marks each) and stores the result in MongoDB.

Run with:
    uvicorn main:app --reload
Then open http://127.0.0.1:8000 in your browser.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict

from services.ollama_service import generate_java_questions, OllamaError
from services.db_service import save_result, get_leaderboard

app = FastAPI(title="Java Quiz App")

# Serve any assets (css/js/images) placed under static/ at /static/...
app.mount("/static", StaticFiles(directory="static"), name="static")

# Marks configuration
NUM_QUESTIONS = 25
MARKS_PER_QUESTION = 4
TOTAL_MARKS = NUM_QUESTIONS * MARKS_PER_QUESTION

# Very small in-memory store: quiz_id -> full question list (with correct answers).
# This is fine for a single-process learning project. For production/multi-worker
# deployments, move this into MongoDB or Redis instead.
QUIZ_CACHE: Dict[str, list] = {}


class AnswerSubmission(BaseModel):
    quiz_id: str
    student_name: str
    answers: Dict[str, str]  # {"0": "A", "1": "C", ...}  (question index -> chosen option)


@app.get("/", response_class=HTMLResponse)
def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/quiz")
def get_quiz():
    """Generate a fresh 25-question Java quiz using Ollama."""
    try:
        quiz_id, questions = generate_java_questions(num_questions=NUM_QUESTIONS)
    except OllamaError as e:
        return JSONResponse(status_code=502, content={"error": str(e)})

    if len(questions) < NUM_QUESTIONS:
        return JSONResponse(
            status_code=502,
            content={
                "error": f"Model only returned {len(questions)} valid questions "
                         f"(needed {NUM_QUESTIONS}). Try again."
            },
        )

    QUIZ_CACHE[quiz_id] = questions

    # Never send correct_answer to the browser.
    public_questions = [
        {"id": i, "question": q["question"], "options": q["options"]}
        for i, q in enumerate(questions)
    ]

    return {
        "quiz_id": quiz_id,
        "questions": public_questions,
        "marks_per_question": MARKS_PER_QUESTION,
        "total_marks": TOTAL_MARKS,
    }


@app.post("/api/submit")
def submit_quiz(submission: AnswerSubmission):
    questions = QUIZ_CACHE.get(submission.quiz_id)
    if not questions:
        return JSONResponse(status_code=404, content={"error": "Quiz not found or expired. Please reload."})

    score = 0
    detailed = []

    for i, q in enumerate(questions):
        given = submission.answers.get(str(i))
        correct = q["correct_answer"]
        is_correct = given == correct
        if is_correct:
            score += MARKS_PER_QUESTION
        detailed.append({
            "question": q["question"],
            "options": q["options"],
            "given_answer": given,
            "correct_answer": correct,
            "is_correct": is_correct,
        })

    result_doc = {
        "student_name": submission.student_name,
        "quiz_id": submission.quiz_id,
        "score": score,
        "total_marks": TOTAL_MARKS,
        "total_questions": len(questions),
        "marks_per_question": MARKS_PER_QUESTION,
        "details": detailed,
    }
    inserted_id = save_result(result_doc)

    # Free the cache entry now that the attempt is graded and stored.
    QUIZ_CACHE.pop(submission.quiz_id, None)

    return {
        "score": score,
        "total_marks": TOTAL_MARKS,
        "result_id": str(inserted_id),
        "details": detailed,
    }


@app.get("/api/leaderboard")
def leaderboard():
    return get_leaderboard()
