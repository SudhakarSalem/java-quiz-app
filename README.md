# Java Quiz App (FastAPI + Ollama + MongoDB)

A 25-question Java MCQ quiz, generated live by a local Ollama model, served
through a FastAPI backend with a plain HTML/JS frontend, with results (4
marks per question, 100 marks total) stored in MongoDB.

## Project structure

```
java-quiz-app/
├── main.py                     FastAPI app (routes)
├── requirements.txt
├── services/
│   ├── ollama_service.py       Calls Ollama, builds & validates the 25 questions
│   └── db_service.py           MongoDB read/write (pymongo)
└── static/
    └── index.html              Quiz UI (HTML/CSS/JS, no framework)
```

## 1. Install dependencies

```bash
cd java-quiz-app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Make sure Ollama has a model pulled

```bash
ollama pull llama3
```

If you use a different model, open `services/ollama_service.py` and change:

```python
MODEL_NAME = "llama3"
```

to whatever `ollama list` shows on your machine (e.g. `llama3.1`, `mistral`,
`qwen2.5-coder`, etc).

## 3. Make sure MongoDB is reachable

By default the app connects to `mongodb://localhost:27017` and uses a
database called `java_quiz_db` with a collection `quiz_results`. To point
at a different instance, set an environment variable before starting the
server:

```bash
export MONGO_URI="mongodb://user:pass@host:27017"
export QUIZ_DB_NAME="java_quiz_db"     # optional
```

## 4. Run the app

```bash
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** in your browser.

## How it works

1. Enter your name and click **Generate Quiz & Start**. The backend
   (`GET /api/quiz`) sends a prompt to Ollama asking for exactly 25 Java
   MCQs as strict JSON, parses/validates the response, and caches the
   correct answers server-side (never sent to the browser).
2. Answer the questions and click **Submit Quiz**
   (`POST /api/submit`). The backend grades each answer at 4 marks,
   computes the total out of 100, and stores a document in MongoDB with
   the student's name, score, and a per-question breakdown.
3. `GET /api/leaderboard` returns the top scores if you want to build a
   leaderboard view later.

## Notes / things you may want to tweak

- **Generation time**: asking a local LLM for 25 well-formed JSON questions
  in one go can take anywhere from a few seconds to a couple of minutes
  depending on your model and hardware. The `requests` timeout is set to
  300s in `ollama_service.py` — increase it if needed.
- **Validation**: if the model returns fewer than 25 valid questions (rare,
  but LLM JSON isn't 100% reliable), `/api/quiz` returns a 502 error asking
  you to retry. You can make this more forgiving by adding a retry loop in
  `generate_java_questions`.
- **Scaling beyond one process**: the current code keeps the "correct
  answers for an in-progress quiz" in an in-memory Python dict
  (`QUIZ_CACHE`). That's fine for local/single-worker use. For multiple
  workers or a real deployment, store the pending quiz in MongoDB instead
  (e.g. a `pending_quizzes` collection) so any worker can grade it.
