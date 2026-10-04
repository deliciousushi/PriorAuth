import sqlite3
import json

from app.config import DATABASE_PATH

def get_connection():
    return sqlite3.connect(
        DATABASE_PATH
    )

def initialize_database():

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS prior_auth_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            treatment TEXT NOT NULL,
            insurer TEXT NOT NULL,
            status TEXT NOT NULL,

            final_decision TEXT,

            matched_requirements INTEGER DEFAULT 0,
            failed_requirements INTEGER DEFAULT 0,
            unknown_requirements INTEGER DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES prior_auth_requests(id)
        )
        """
    )

    connection.commit()
    connection.close()


def create_request(
    patient_id: str,
    treatment: str,
    insurer: str,
):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO prior_auth_requests
        (
            patient_id,
            treatment,
            insurer,
            status
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            patient_id,
            treatment,
            insurer,
            "CREATED"
        )
    )

    connection.commit()

    request_id = cursor.lastrowid

    connection.close()

    return request_id


def update_request_result(
    request_id: int,
    final_decision: str,
    matched_requirements: int,
    failed_requirements: int,
    unknown_requirements: int,
):
    connection = get_connection()
    cursor = connection.cursor()

    if final_decision in ("PASS", "FAIL"):
        status = "COMPLETED"
    else:
        status = "REVIEW_REQUIRED"

    cursor.execute(
        """
        UPDATE prior_auth_requests
        SET
            status = ?,
            final_decision = ?,
            matched_requirements = ?,
            failed_requirements = ?,
            unknown_requirements = ?
        WHERE id = ?
        """,
        (
            status,
            final_decision,
            matched_requirements,
            failed_requirements,
            unknown_requirements,
            request_id,
        ),
    )

    connection.commit()
    connection.close()


def mark_request_failed(request_id: int, error_message: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE prior_auth_requests
        SET 
            status = ?,
            final_decision = ?
        WHERE id = ?
        """,
        ("FAILED",
         error_message,
         request_id,
        ),
    )
    connection.commit()
    connection.close()

def add_audit_log(request_id: int, event_type: str, message: str):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO audit_logs
        (
            request_id,
            event_type,
            message
        )
        VALUES (?, ?, ?)
        """,
        (
            request_id,
            event_type,
            message
        ),
    )

    connection.commit()
    connection.close()