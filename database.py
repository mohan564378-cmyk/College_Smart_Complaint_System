import sqlite3
from flask import current_app


def get_db():
    connection = sqlite3.connect(
        current_app.config["DATABASE"],
        timeout=10
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_db(app):
    with app.app_context():
        connection = get_db()

        connection.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                register_number TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                department TEXT NOT NULL,
                year_of_study INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                complaint_code TEXT UNIQUE NOT NULL,
                student_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                location TEXT NOT NULL,
                description TEXT NOT NULL,

                priority TEXT NOT NULL DEFAULT 'Medium'
                    CHECK(priority IN ('Low', 'Medium', 'High')),

                status TEXT NOT NULL DEFAULT 'Pending'
                    CHECK(status IN (
                        'Pending',
                        'In Progress',
                        'Resolved',
                        'Rejected'
                    )),

                admin_response TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(student_id)
                    REFERENCES students(id)
                    ON DELETE RESTRICT
            );

            CREATE INDEX IF NOT EXISTS idx_complaints_student
                ON complaints(student_id);

            CREATE INDEX IF NOT EXISTS idx_complaints_status
                ON complaints(status);

            CREATE INDEX IF NOT EXISTS idx_complaints_category
                ON complaints(category);
        """)

        connection.commit()
        connection.close()