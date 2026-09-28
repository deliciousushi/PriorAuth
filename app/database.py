import json
import sqlite3
from datetime import datetime

from app.config import DATABASE_PATH


def get_connection():
    return sqlite3.connect(DATABASE_PATH)


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prior_auth_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            treatment TEXT NOT NULL,
            insurer TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            draft_json TEXT,
            validation_result TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            event TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(request_id)
                REFERENCES prior_auth_requests(id)
        )
    """)

    connection.commit()
    connection.close()


def create_request(
    patient_id: str,
    treatment: str,
    insurer: str
):
    connection = get_connection()
    cursor = connection.cursor()

    now = datetime.utcnow().isoformat()

    cursor.execute(
        """
        INSERT INTO prior_auth_requests
        (
            patient_id,
            treatment,
            insurer,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            patient_id,
            treatment,
            insurer,
            "PROCESSING",
            now
        )
    )

    request_id = cursor.lastrowid

    connection.commit()
    connection.close()

    add_audit_log(
        request_id,
        "REQUEST_CREATED",
        "Prior authorization workflow started."
    )

    return request_id


def update_request(
    request_id: int,
    status: str,
    draft=None,
    validation_result=None
):
    connection = get_connection()
    cursor = connection.cursor()

    draft_json = None

    if draft is not None:
        draft_json = json.dumps(
            draft.model_dump()
            if hasattr(draft, "model_dump")
            else draft
        )

    cursor.execute(
        """
        UPDATE prior_auth_requests
        SET
            status = ?,
            completed_at = ?,
            draft_json = ?,
            validation_result = ?
        WHERE id = ?
        """,
        (
            status,
            datetime.utcnow().isoformat(),
            draft_json,
            validation_result,
            request_id
        )
    )

    connection.commit()
    connection.close()


def add_audit_log(
    request_id: int,
    event: str,
    details: str = ""
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO audit_logs
        (
            request_id,
            event,
            details,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            request_id,
            event,
            details,
            datetime.utcnow().isoformat()
        )
    )

    connection.commit()
    connection.close()


def get_recent_requests(limit: int = 10):

    connection = get_connection()
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT *
        FROM prior_auth_requests
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]
