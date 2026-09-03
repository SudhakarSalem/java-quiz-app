"""
MongoDB access for storing and reading quiz results.
Uses the MONGO_URI env var if set, otherwise defaults to a local instance.
"""

import os
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

MONGO_URI = "mongodb+srv://sudhakarsalem_db_user:password@cluster0.teatimw.mongodb.net/"
DB_NAME = os.environ.get("QUIZ_DB_NAME", "test_db")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
results_collection = db["user_scores"]


def save_result(result_doc: dict):
    """Insert a graded quiz attempt and return its inserted _id."""
    result_doc["timestamp"] = datetime.now(timezone.utc)
    inserted = results_collection.insert_one(result_doc)
    return inserted.inserted_id


def get_leaderboard(limit: int = 10):
    """Return the top N attempts by score, most recent first as a tiebreaker."""
    cursor = (
        results_collection.find(
            {},
            {"student_name": 1, "score": 1, "total_marks": 1, "timestamp": 1, "_id": 0},
        )
        .sort([("score", DESCENDING), ("timestamp", DESCENDING)])
        .limit(limit)
    )
    docs = list(cursor)
    for d in docs:
        if "timestamp" in d:
            d["timestamp"] = d["timestamp"].isoformat()
    return docs
