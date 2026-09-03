"""
Talks to a locally running Ollama server to generate Java MCQs as JSON.
Assumes Ollama is running on the default port (http://localhost:11434)
and that the model named MODEL_NAME has already been pulled, e.g.:

    ollama pull llama3
"""

import json
import re
import uuid
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"

# Change this to whatever model you have pulled locally (check with `ollama list`).
MODEL_NAME = "llama3.2:latest"

PROMPT_TEMPLATE = """You are a GENERAL KNOWLEDGE expert creating a multiple choice quiz.

Generate exactly {n} multiple choice questions about the GENERAL KNOWLEDGE.
Cover a good mix of topics: sports, latest news, science, geographics etc.
Every question must have exactly one correct answer among 4 options.

Respond with ONLY a single valid JSON object and nothing else - no explanation, no
markdown code fences, no extra commentary before or after it.

The JSON object must have exactly one key, "questions", whose value is an array of
exactly {n} question objects. Each question object must have exactly these keys:
- "question": string
- "options": object with keys "A", "B", "C", "D" mapping to the answer text
- "correct_answer": one of "A", "B", "C", "D"

Example of the required shape (showing 1 question, you must output {n}):
Which planet in our solar system rotates clockwise on its axis, unlike most other planets?A) MarsB) VenusC) JupiterD) Neptune
{{"questions": [{{"question": "Which planet in our solar system rotates clockwise on its axis, unlike most other planets?", "options": {{"A": "Mars", "B": "Venus", "C": "jupiter", "D": "neptune"}}, "correct_answer": "B"}}]}}
"""


class OllamaError(Exception):
    """Raised when Ollama can't be reached or returns unusable output."""
    pass


def _extract_questions(text: str):
    text = text.strip()
    # Strip common markdown code-fence wrapping in case the model added it anyway.
    cleaned = re.sub(r"^```(json)?", "", text, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    # Preferred shape: a JSON object with a "questions" key.
    obj_start, obj_end = cleaned.find("{"), cleaned.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        try:
            parsed = json.loads(cleaned[obj_start:obj_end + 1])
            if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
                return parsed["questions"]
        except json.JSONDecodeError:
            pass  # fall through and try a bare array instead

    # Fallback shape: a bare JSON array.
    arr_start, arr_end = cleaned.find("["), cleaned.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        try:
            return json.loads(cleaned[arr_start:arr_end + 1])
        except json.JSONDecodeError:
            pass

    snippet = text[:400].replace("\n", " ")
    raise OllamaError(
        "Could not find a JSON questions array in the model's response. "
        f"Raw output started with: {snippet!r}"
    )


def _is_valid_question(q) -> bool:
    if not isinstance(q, dict):
        return False
    if "question" not in q or "options" not in q or "correct_answer" not in q:
        return False
    options = q["options"]
    if not isinstance(options, dict):
        return False
    if not {"A", "B", "C", "D"}.issubset(options.keys()):
        return False
    if q["correct_answer"] not in options:
        return False
    return True


def generate_java_questions(num_questions: int = 25, model: str = MODEL_NAME):
    """
    Returns (quiz_id, questions) where questions is a list of dicts:
        {"question": str, "options": {"A":.., "B":.., "C":.., "D":..}, "correct_answer": "A"}
    Raises OllamaError on connection or parsing failure.
    """
    prompt = PROMPT_TEMPLATE.format(n=num_questions)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",  # ask Ollama to constrain output to valid JSON
        "options": {"temperature": 0.5},
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=300)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(
            "Could not connect to Ollama at http://localhost:11434. "
            "Make sure 'ollama serve' is running."
        ) from e
    except requests.exceptions.RequestException as e:
        raise OllamaError(f"Ollama request failed: {e}") from e

    data = response.json()
    raw_text = data.get("response", "")
    print(f"[ollama_service] raw model output ({len(raw_text)} chars):\n{raw_text}\n")

    try:
        raw_questions = _extract_questions(raw_text)
    except (ValueError, json.JSONDecodeError) as e:
        raise OllamaError(f"Model output was not valid JSON: {e}") from e

    if not isinstance(raw_questions, list):
        raise OllamaError("Model's 'questions' field was not a JSON array.")

    valid_questions = [q for q in raw_questions if _is_valid_question(q)]

    quiz_id = str(uuid.uuid4())
    return quiz_id, valid_questions[:num_questions]
