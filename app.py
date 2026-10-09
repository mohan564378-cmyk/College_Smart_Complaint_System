import os
import re
import secrets
import sqlite3
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, abort
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from config import Config
from database import get_db, init_db


app = Flask(__name__)
app.config.from_object(Config)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

init_db(app)


# =====================================================
# CONSTANTS
# =====================================================

CATEGORIES = [
    "Classroom",
    "Laboratory",
    "Library",
    "Hostel",
    "Transport",
    "Canteen",
    "Cleanliness",
    "Electricity",
    "Water Supply",
    "Internet",
    "Other"
]

DEPARTMENTS = [
    "Computer Science",
    "Information Technology",
    "Commerce",
    "Mathematics",
    "Physics",
    "Chemistry",
    "English",
    "Other"
]

STATUSES = [
    "Pending",
    "In Progress",
    "Resolved",
    "Rejected"
]

PRIORITIES = ["Low", "Medium", "High"]


# =====================================================
# DATABASE HELPERS
# =====================================================

def fetch_one(query, parameters=()):
    connection = get_db()

    try:
        return connection.execute(
            query, parameters
        ).fetchone()
    finally:
        connection.close()


def fetch_all(query, parameters=()):
    connection = get_db()

    try:
        return connection.execute(
            query, parameters
        ).fetchall()
    finally:
        connection.close()


def execute_query(query, parameters=()):
    connection = get_db()

    try:
        cursor = connection.execute(
            query, parameters
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def complaint_statistics(student_id=None):
    connection = get_db()

    try:
        where = ""
        parameters = ()

        if student_id is not None:
            where = "WHERE student_id = ?"
            parameters = (student_id,)

        total = connection.execute(
            f"SELECT COUNT(*) AS total FROM complaints {where}",
            parameters
        ).fetchone()["total"]

        stats = {"total": total}

        for status in STATUSES:
            condition = f"{where} {'AND' if where else 'WHERE'} status = ?"

            row = connection.execute(
                f"SELECT COUNT(*) AS total FROM complaints {condition}",
                parameters + (status,)
            ).fetchone()

            stats[status.lower().replace(" ", "_")] = row["total"]

        return stats

    finally:
        connection.close()


# =====================================================
# AUTHENTICATION
# =====================================================

def student_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("student_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


def admin_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("Administrator login is required.", "warning")
            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


# =====================================================
# HOME
# =====================================================

@app.route("/")
def home():
    statistics = complaint_statistics()

    return render_template(
        "index.html",
        statistics=statistics
    )


# =====================================================
# REGISTER
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("student_id"):
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        register_number = request.form.get(
            "register_number", ""
        ).strip().upper()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password", ""
        )

        department = request.form.get("department", "")
        year = request.form.get("year_of_study", "")

        if not all([
            name, register_number, email,
            password, confirm_password, department, year
        ]):
            flash("Please fill in all fields.", "danger")

        elif len(name) > 100 or len(register_number) > 30:
            flash("Name or register number is too long.", "danger")

        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Enter a valid email address.", "danger")

        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")

        elif password != confirm_password:
            flash("Passwords do not match.", "danger")

        elif department not in DEPARTMENTS:
            flash("Select a valid department.", "danger")

        else:
            try:
                year_number = int(year)

                if year_number not in (1, 2, 3, 4, 5, 6):
                    raise ValueError

                execute_query(
                    """
                    INSERT INTO students (
                        name, register_number, email,
                        password_hash, department, year_of_study
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        register_number,
                        email,
                        generate_password_hash(password),
                        department,
                        year_number
                    )
                )

                flash(
                    "Registration successful. You can now log in.",
                    "success"
                )

                return redirect(url_for("login"))

            except ValueError:
                flash("Select a valid year of study.", "danger")

            except sqlite3.IntegrityError:
                flash(
                    "Register number or email already exists.",
                    "danger"
                )

    return render_template(
        "register.html",
        departments=DEPARTMENTS
    )


# =====================================================
# STUDENT LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("student_id"):
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        student = fetch_one(
            "SELECT * FROM students WHERE email = ?",
            (email,)
        )

        if (
            student
            and check_password_hash(
                student["password_hash"], password
            )
        ):
            session.clear()
            session["student_id"] = student["id"]
            session["student_name"] = student["name"]

            flash("Welcome back!", "success")

            return redirect(url_for("student_dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


# =====================================================
# STUDENT DASHBOARD
# =====================================================

@app.route("/student/dashboard")
@student_required
def student_dashboard():
    student_id = session["student_id"]

    statistics = complaint_statistics(student_id)

    complaints = fetch_all(
        """
        SELECT *
        FROM complaints
        WHERE student_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 5
        """,
        (student_id,)
    )

    return render_template(
        "student_dashboard.html",
        statistics=statistics,
        complaints=complaints
    )


# =====================================================
# SUBMIT COMPLAINT
# =====================================================

@app.route("/complaints/new", methods=["GET", "POST"])
@student_required
def submit_complaint():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "")
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "Medium")

        if not all([title, category, location, description]):
            flash("Please complete every required field.", "danger")

        elif len(title) > 200 or len(location) > 200:
            flash("Title or location is too long.", "danger")

        elif category not in CATEGORIES:
            flash("Select a valid category.", "danger")

        elif priority not in PRIORITIES:
            flash("Select a valid priority.", "danger")

        elif len(description) > 10000:
            flash("Description is too long.", "danger")

        else:
            code = "CMP-" + secrets.token_hex(5).upper()

            execute_query(
                """
                INSERT INTO complaints (
                    complaint_code, student_id, title,
                    category, location, description, priority
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    session["student_id"],
                    title,
                    category,
                    location,
                    description,
                    priority
                )
            )

            flash(
                f"Complaint submitted successfully. ID: {code}",
                "success"
            )

            return redirect(url_for("my_complaints"))

    return render_template(
        "submit_complaint.html",
        categories=CATEGORIES,
        priorities=PRIORITIES
    )


# =====================================================
# STUDENT COMPLAINTS
# =====================================================

@app.route("/complaints")
@student_required
def my_complaints():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")
    category = request.args.get("category", "")

    query = """
        SELECT *
        FROM complaints
        WHERE student_id = ?
    """

    parameters = [session["student_id"]]

    if search:
        query += " AND (complaint_code LIKE ? OR title LIKE ?)"
        parameters.extend([f"%{search}%", f"%{search}%"])

    if status in STATUSES:
        query += " AND status = ?"
        parameters.append(status)

    if category in CATEGORIES:
        query += " AND category = ?"
        parameters.append(category)

    query += " ORDER BY created_at DESC, id DESC"

    complaints = fetch_all(query, tuple(parameters))

    return render_template(
        "complaints.html",
        complaints=complaints,
        search=search,
        selected_status=status,
        selected_category=category,
        statuses=STATUSES,
        categories=CATEGORIES
    )


@app.route("/complaints/<int:complaint_id>")
@student_required
def complaint_detail(complaint_id):
    complaint = fetch_one(
        """
        SELECT *
        FROM complaints
        WHERE id = ? AND student_id = ?
        """,
        (complaint_id, session["student_id"])
    )

    if complaint is None:
        abort(404)

    return render_template(
        "complaint_detail.html",
        complaint=complaint
    )


# =====================================================
# ADMIN LOGIN
# =====================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if (
            secrets.compare_digest(
                username, app.config["ADMIN_USERNAME"]
            )
            and secrets.compare_digest(
                password, app.config["ADMIN_PASSWORD"]
            )
        ):
            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username

            flash("Administrator login successful.", "success")

            return redirect(url_for("admin_dashboard"))

        flash("Invalid administrator credentials.", "danger")

    return render_template("admin_login.html")


@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    flash("Administrator logged out.", "info")
    return redirect(url_for("home"))


# =====================================================
# ADMIN DASHBOARD
# =====================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "")
    category = request.args.get("category", "")

    statistics = complaint_statistics()

    query = """
        SELECT
            complaints.*,
            students.name AS student_name,
            students.register_number,
            students.department,
            students.email
        FROM complaints
        JOIN students ON students.id = complaints.student_id
        WHERE 1 = 1
    """

    parameters = []

    if search:
        query += """
            AND (
                complaints.complaint_code LIKE ?
                OR complaints.title LIKE ?
                OR students.name LIKE ?
                OR students.register_number LIKE ?
            )
        """

        term = f"%{search}%"
        parameters.extend([term, term, term, term])

    if status in STATUSES:
        query += " AND complaints.status = ?"
        parameters.append(status)

    if category in CATEGORIES:
        query += " AND complaints.category = ?"
        parameters.append(category)

    query += " ORDER BY complaints.created_at DESC, complaints.id DESC"

    complaints = fetch_all(query, tuple(parameters))

    return render_template(
        "admin_dashboard.html",
        statistics=statistics,
        complaints=complaints,
        search=search,
        selected_status=status,
        selected_category=category,
        statuses=STATUSES,
        categories=CATEGORIES
    )


# =====================================================
# ADMIN COMPLAINT DETAIL
# =====================================================

@app.route(
    "/admin/complaints/<int:complaint_id>",
    methods=["GET", "POST"]
)
@admin_required
def admin_complaint_detail(complaint_id):
    complaint = fetch_one(
        """
        SELECT
            complaints.*,
            students.name AS student_name,
            students.email,
            students.register_number,
            students.department,
            students.year_of_study
        FROM complaints
        JOIN students ON students.id = complaints.student_id
        WHERE complaints.id = ?
        """,
        (complaint_id,)
    )

    if complaint is None:
        abort(404)

    if request.method == "POST":
        status = request.form.get("status", "")
        response = request.form.get(
            "admin_response", ""
        ).strip()

        if status not in STATUSES:
            flash("Select a valid complaint status.", "danger")

        elif len(response) > 5000:
            flash("The response is too long.", "danger")

        else:
            execute_query(
                """
                UPDATE complaints
                SET
                    status = ?,
                    admin_response = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, response, complaint_id)
            )

            flash("Complaint updated successfully.", "success")

            return redirect(
                url_for(
                    "admin_complaint_detail",
                    complaint_id=complaint_id
                )
            )

    return render_template(
        "admin_complaint_detail.html",
        complaint=complaint,
        statuses=STATUSES
    )


# =====================================================
# ERROR PAGES
# =====================================================

@app.errorhandler(404)
def not_found(error):
    return render_template(
        "error.html",
        code=404,
        message="The requested page could not be found."
    ), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template(
        "error.html",
        code=500,
        message="Something went wrong. Please try again."
    ), 500


# =====================================================
# RUN APPLICATION
# =====================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )