from datetime import datetime, timedelta
from functools import wraps
import os
import sqlite3

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-development-secret-before-deployment")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            duration_minutes INTEGER NOT NULL CHECK(duration_minutes BETWEEN 1 AND 300),
            is_published INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL CHECK(correct_option IN ('A','B','C','D')),
            marks INTEGER NOT NULL DEFAULT 1 CHECK(marks BETWEEN 1 AND 100)
        );
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL REFERENCES exams(id),
            student_id INTEGER NOT NULL REFERENCES users(id),
            started_at TEXT NOT NULL,
            deadline_at TEXT NOT NULL,
            submitted_at TEXT,
            score INTEGER,
            total_marks INTEGER NOT NULL,
            UNIQUE(exam_id, student_id)
        );
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL REFERENCES questions(id),
            selected_option TEXT CHECK(selected_option IN ('A','B','C','D') OR selected_option IS NULL),
            UNIQUE(attempt_id, question_id)
        );
        """)
        # Demo accounts make the project easy to run locally. Change these passwords before deployment.
        seeds = [
            ("Project Admin", "admin@example.com", "Admin@123", "admin"),
            ("Demo Teacher", "teacher@example.com", "Teacher@123", "teacher"),
            ("Demo Student", "student@example.com", "Student@123", "student"),
        ]
        for name, email, password, role in seeds:
            existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if not existing:
                db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                           (name, email, generate_password_hash(password), role))
        admin = db.execute("SELECT id FROM users WHERE email='admin@example.com'").fetchone()
        if not db.execute("SELECT id FROM exams LIMIT 1").fetchone():
            cur = db.execute("""INSERT INTO exams(title,description,duration_minutes,is_published,created_by)
                                VALUES(?,?,?,?,?)""",
                             ("Python Fundamentals", "Demo exam: variables, loops, and data types.", 10, 1, admin["id"]))
            exam_id = cur.lastrowid
            questions = [
                ("Which keyword defines a function in Python?", "func", "def", "function", "define", "B", 1),
                ("Which data type stores key-value pairs?", "List", "Tuple", "Dictionary", "Set", "C", 1),
                ("What is the result of 3 // 2?", "1.5", "1", "2", "0", "B", 1),
            ]
            db.executemany("""INSERT INTO questions(exam_id,question_text,option_a,option_b,option_c,option_d,correct_option,marks)
                              VALUES(?,?,?,?,?,?,?,?)""",
                           [(exam_id, *q) for q in questions])


def current_user():
    if "user_id" not in session:
        return None
    with get_db() as db:
        return db.execute("SELECT id,name,email,role FROM users WHERE id=?", (session["user_id"],)).fetchone()


def login_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if roles and user["role"] not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def parse_time(value):
    return datetime.fromisoformat(value)


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email; password must be at least 8 characters.", "danger")
            return render_template("register.html")
        try:
            with get_db() as db:
                db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                           (name, email, generate_password_hash(password), "student"))
            flash("Account created. You can now log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email address is already registered.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required()
def dashboard():
    user = current_user()
    with get_db() as db:
        if user["role"] in ("admin", "teacher"):
            stats = {
                "students": db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
                "exams": db.execute("SELECT COUNT(*) FROM exams").fetchone()[0],
                "attempts": db.execute("SELECT COUNT(*) FROM attempts WHERE submitted_at IS NOT NULL").fetchone()[0],
                "average": db.execute("SELECT ROUND(AVG(100.0*score/NULLIF(total_marks,0)),1) FROM attempts WHERE submitted_at IS NOT NULL").fetchone()[0] or 0,
            }
            exams = db.execute("""SELECT e.*, u.name AS creator,
                (SELECT COUNT(*) FROM questions q WHERE q.exam_id=e.id) AS question_count,
                (SELECT COUNT(*) FROM attempts a WHERE a.exam_id=e.id AND a.submitted_at IS NOT NULL) AS completed_count
                FROM exams e JOIN users u ON u.id=e.created_by ORDER BY e.created_at DESC""").fetchall()
            results = db.execute("""SELECT a.id, u.name AS student_name, e.title AS exam_title, a.score, a.total_marks,
                ROUND(100.0*a.score/NULLIF(a.total_marks,0),1) AS percentage, a.submitted_at
                FROM attempts a JOIN users u ON u.id=a.student_id JOIN exams e ON e.id=a.exam_id
                WHERE a.submitted_at IS NOT NULL ORDER BY a.submitted_at DESC LIMIT 10""").fetchall()
            return render_template("staff_dashboard.html", stats=stats, exams=exams, results=results)
        exams = db.execute("""SELECT e.*,
            (SELECT COUNT(*) FROM questions q WHERE q.exam_id=e.id) AS question_count,
            a.id AS attempt_id, a.score, a.total_marks, a.submitted_at
            FROM exams e LEFT JOIN attempts a ON a.exam_id=e.id AND a.student_id=?
            WHERE e.is_published=1 ORDER BY e.created_at DESC""", (user["id"],)).fetchall()
        history = db.execute("""SELECT e.title, a.score, a.total_marks,
            ROUND(100.0*a.score/NULLIF(a.total_marks,0),1) AS percentage, a.submitted_at
            FROM attempts a JOIN exams e ON e.id=a.exam_id
            WHERE a.student_id=? AND a.submitted_at IS NOT NULL ORDER BY a.submitted_at DESC""",
            (user["id"],)).fetchall()
        return render_template("student_dashboard.html", exams=exams, history=history)


@app.route("/exams/new", methods=["GET", "POST"])
@login_required("admin", "teacher")
def create_exam():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        try:
            duration = int(request.form.get("duration_minutes", "0"))
        except ValueError:
            duration = 0
        if not title or not 1 <= duration <= 300:
            flash("Provide a title and duration from 1 to 300 minutes.", "danger")
            return render_template("exam_form.html")
        with get_db() as db:
            db.execute("INSERT INTO exams(title,description,duration_minutes,is_published,created_by) VALUES(?,?,?,?,?)",
                       (title, description, duration, 0, session["user_id"]))
            exam_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        flash("Exam created. Add questions before publishing it.", "success")
        return redirect(url_for("manage_questions", exam_id=exam_id))
    return render_template("exam_form.html")


@app.route("/exams/<int:exam_id>/questions", methods=["GET", "POST"])
@login_required("admin", "teacher")
def manage_questions(exam_id):
    with get_db() as db:
        exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not exam:
            abort(404)
        if request.method == "POST":
            qtext = request.form.get("question_text", "").strip()
            opts = [request.form.get(f"option_{x.lower()}", "").strip() for x in "ABCD"]
            correct = request.form.get("correct_option", "")
            try:
                marks = int(request.form.get("marks", "1"))
            except ValueError:
                marks = 0
            if not qtext or not all(opts) or correct not in "ABCD" or not 1 <= marks <= 100:
                flash("Fill every question and option; select a valid answer and marks.", "danger")
            else:
                db.execute("""INSERT INTO questions(exam_id,question_text,option_a,option_b,option_c,option_d,correct_option,marks)
                               VALUES(?,?,?,?,?,?,?,?)""", (exam_id, qtext, *opts, correct, marks))
                flash("Question added.", "success")
                return redirect(url_for("manage_questions", exam_id=exam_id))
        questions = db.execute("SELECT * FROM questions WHERE exam_id=? ORDER BY id", (exam_id,)).fetchall()
    return render_template("questions.html", exam=exam, questions=questions)


@app.route("/questions/<int:question_id>/delete", methods=["POST"])
@login_required("admin", "teacher")
def delete_question(question_id):
    with get_db() as db:
        question = db.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
        if not question:
            abort(404)
        exam_id = question["exam_id"]
        exam = db.execute("SELECT is_published FROM exams WHERE id=?", (exam_id,)).fetchone()
        if exam["is_published"]:
            flash("Unpublish the exam before changing questions.", "warning")
        else:
            db.execute("DELETE FROM questions WHERE id=?", (question_id,))
            flash("Question deleted.", "info")
    return redirect(url_for("manage_questions", exam_id=exam_id))


@app.route("/exams/<int:exam_id>/publish", methods=["POST"])
@login_required("admin", "teacher")
def toggle_publish(exam_id):
    with get_db() as db:
        exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
        if not exam:
            abort(404)
        count = db.execute("SELECT COUNT(*) FROM questions WHERE exam_id=?", (exam_id,)).fetchone()[0]
        if not exam["is_published"] and count == 0:
            flash("Add at least one question before publishing.", "danger")
        else:
            new_state = 0 if exam["is_published"] else 1
            db.execute("UPDATE exams SET is_published=? WHERE id=?", (new_state, exam_id))
            flash("Exam " + ("published." if new_state else "unpublished."), "success")
    return redirect(url_for("dashboard"))


@app.route("/exams/<int:exam_id>/start", methods=["GET", "POST"])
@login_required("student")
def take_exam(exam_id):
    student_id = session["user_id"]
    with get_db() as db:
        exam = db.execute("SELECT * FROM exams WHERE id=? AND is_published=1", (exam_id,)).fetchone()
        if not exam:
            abort(404)
        attempt = db.execute("SELECT * FROM attempts WHERE exam_id=? AND student_id=?", (exam_id, student_id)).fetchone()
        if attempt and attempt["submitted_at"]:
            flash("You have already submitted this exam.", "info")
            return redirect(url_for("dashboard"))
        if not attempt:
            questions = db.execute("SELECT id,marks FROM questions WHERE exam_id=? ORDER BY id", (exam_id,)).fetchall()
            if not questions:
                flash("This exam has no questions yet.", "warning")
                return redirect(url_for("dashboard"))
            now = datetime.now()
            deadline = now + timedelta(minutes=exam["duration_minutes"])
            total = sum(q["marks"] for q in questions)
            cur = db.execute("""INSERT INTO attempts(exam_id,student_id,started_at,deadline_at,total_marks)
                                VALUES(?,?,?,?,?)""",
                             (exam_id, student_id, now.isoformat(timespec="seconds"),
                              deadline.isoformat(timespec="seconds"), total))
            attempt_id = cur.lastrowid
            db.executemany("INSERT INTO answers(attempt_id,question_id) VALUES(?,?)",
                           [(attempt_id, q["id"]) for q in questions])
            attempt = db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
        if parse_time(attempt["deadline_at"]) <= datetime.now():
            _submit_attempt(db, attempt["id"])
            flash("The time limit has expired; your exam was submitted.", "warning")
            return redirect(url_for("dashboard"))
        questions = db.execute("""SELECT q.id,q.question_text,q.option_a,q.option_b,q.option_c,q.option_d,q.marks,
                                  a.selected_option FROM questions q JOIN answers a ON a.question_id=q.id
                                  WHERE q.exam_id=? AND a.attempt_id=? ORDER BY q.id""",
                               (exam_id, attempt["id"])).fetchall()
    return render_template("take_exam.html", exam=exam, attempt=attempt, questions=questions)


def _submit_attempt(db, attempt_id):
    attempt = db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone()
    if not attempt or attempt["submitted_at"]:
        return
    answers = db.execute("""SELECT a.selected_option,q.correct_option,q.marks FROM answers a
                             JOIN questions q ON q.id=a.question_id WHERE a.attempt_id=?""",
                          (attempt_id,)).fetchall()
    score = sum(row["marks"] for row in answers
                if row["selected_option"] and row["selected_option"] == row["correct_option"])
    db.execute("UPDATE attempts SET score=?,submitted_at=? WHERE id=?",
               (score, datetime.now().isoformat(timespec="seconds"), attempt_id))


@app.route("/exams/<int:exam_id>/save-answer", methods=["POST"])
@login_required("student")
def save_answer(exam_id):
    question_id = request.form.get("question_id", type=int)
    selected = request.form.get("selected_option", "")
    if selected not in ("A", "B", "C", "D", ""):
        abort(400)
    with get_db() as db:
        attempt = db.execute("SELECT * FROM attempts WHERE exam_id=? AND student_id=?",
                             (exam_id, session["user_id"])).fetchone()
        if not attempt or attempt["submitted_at"] or parse_time(attempt["deadline_at"]) <= datetime.now():
            return {"ok": False, "error": "Attempt is not active."}, 409
        result = db.execute("""UPDATE answers SET selected_option=? WHERE attempt_id=? AND question_id=?
                               AND question_id IN (SELECT id FROM questions WHERE exam_id=?)""",
                            (selected or None, attempt["id"], question_id, exam_id))
        if result.rowcount != 1:
            abort(400)
    return {"ok": True}


@app.route("/exams/<int:exam_id>/submit", methods=["POST"])
@login_required("student")
def submit_exam(exam_id):
    with get_db() as db:
        attempt = db.execute("SELECT * FROM attempts WHERE exam_id=? AND student_id=?",
                             (exam_id, session["user_id"])).fetchone()
        if not attempt:
            abort(404)
        _submit_attempt(db, attempt["id"])
        flash("Exam submitted successfully.", "success")
    return redirect(url_for("result", attempt_id=attempt["id"]))


@app.route("/results/<int:attempt_id>")
@login_required()
def result(attempt_id):
    user = current_user()
    with get_db() as db:
        query = """SELECT a.*, e.title AS exam_title, u.name AS student_name
                   FROM attempts a JOIN exams e ON e.id=a.exam_id JOIN users u ON u.id=a.student_id
                   WHERE a.id=?"""
        attempt = db.execute(query, (attempt_id,)).fetchone()
        if not attempt:
            abort(404)
        if user["role"] == "student" and attempt["student_id"] != user["id"]:
            abort(403)
        if not attempt["submitted_at"]:
            flash("This attempt has not been submitted yet.", "warning")
            return redirect(url_for("dashboard"))
        percentage = round(100 * attempt["score"] / attempt["total_marks"], 1) if attempt["total_marks"] else 0
        answers = db.execute("""SELECT q.question_text,q.option_a,q.option_b,q.option_c,q.option_d,q.correct_option,
                                a.selected_option,q.marks FROM answers a JOIN questions q ON q.id=a.question_id
                                WHERE a.attempt_id=? ORDER BY q.id""", (attempt_id,)).fetchall()
    return render_template("result.html", attempt=attempt, percentage=percentage, answers=answers)


@app.route("/admin/users", methods=["GET", "POST"])
@login_required("admin")
def manage_users():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        if not name or not email or len(password) < 8 or role not in ("teacher", "student"):
            flash("Provide valid details. Password must be at least 8 characters.", "danger")
        else:
            try:
                with get_db() as db:
                    db.execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
                               (name, email, generate_password_hash(password), role))
                flash(f"{role.title()} account created.", "success")
                return redirect(url_for("manage_users"))
            except sqlite3.IntegrityError:
                flash("Email already exists.", "danger")
    with get_db() as db:
        users = db.execute("SELECT id,name,email,role,created_at FROM users ORDER BY role,name").fetchall()
    return render_template("users.html", users=users)


@app.route("/admin/results.csv")
@login_required("admin", "teacher")
def export_results():
    import csv
    from io import StringIO
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student", "Email", "Exam", "Score", "Total Marks", "Percentage", "Submitted At"])
    with get_db() as db:
        rows = db.execute("""SELECT u.name,u.email,e.title,a.score,a.total_marks,
            ROUND(100.0*a.score/NULLIF(a.total_marks,0),1),a.submitted_at
            FROM attempts a JOIN users u ON u.id=a.student_id JOIN exams e ON e.id=a.exam_id
            WHERE a.submitted_at IS NOT NULL ORDER BY a.submitted_at DESC""").fetchall()
    writer.writerows([tuple(r) for r in rows])
    from flask import Response
    return Response("\\ufeff" + output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=exam_results.csv"})


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to access this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The requested page was not found."), 404


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
