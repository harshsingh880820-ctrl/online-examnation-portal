# Online Examination Portal (BCA Final-Year Project)

A runnable Flask + SQLite examination portal with student registration, admin/teacher tools, timed MCQ exams, server-side scoring, result history, and CSV export.

## Requirements
- Python 3.10+
- Internet connection on first page load for Bootstrap CDN (optional; local CSS and JS are included, but Bootstrap is loaded from CDN).

## Setup (Windows / VS Code)
1. Extract the ZIP file and open the `online_examination_portal` folder in VS Code.
2. Open Terminal → New Terminal.
3. Create a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, use `.\.venv\Scripts\activate.bat` in Command Prompt or run `python -m venv .venv` and use your installed Python interpreter.
4. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
5. Start the app:
   ```bash
   python app.py
   ```
6. Open `http://127.0.0.1:5000` in your browser. The SQLite database is created automatically on first start.

## Demo accounts
- Admin: `admin@example.com` / `Admin@123`
- Teacher: `teacher@example.com` / `Teacher@123`
- Student: `student@example.com` / `Student@123`

Change demo passwords and set a strong `SECRET_KEY` before any deployment. This demo is for local coursework, not a hardened production exam service.

## First run walkthrough
1. Log in as admin and open **Manage users** to create a teacher account if desired.
2. Log in as teacher (or admin) and create an exam.
3. Add at least one MCQ, choose the correct option and marks, then publish the exam.
4. Log out and log in as student, or register a new student.
5. Start the published exam. Select answers; the portal saves each selection to the server.
6. Submit before time expires, or wait for the timer to submit automatically.
7. View results on the student dashboard. Staff can inspect results and download `exam_results.csv`.

## Database
`database.db` is created by `init_db()` with `users`, `exams`, `questions`, `attempts`, and `answers` tables. Demo accounts and a sample Python Fundamentals exam are seeded only when missing. To reset the local demo database, stop the server and delete `database.db`, then run the app again.

## Tests
Run:
```bash
python -m unittest discover -s tests -v
```

## Features
- Role-based admin, teacher, and student access
- Hashed passwords
- Exam creation, question management, publish/unpublish
- One attempt per student per exam
- Countdown timer and automatic submission
- Server-side answer saving and scoring
- Student result history and staff result dashboard
- CSV result export

## Important limitations / next improvements
- The demo has no email verification, password reset, rate limiting, or full CSRF protection; add these before real-world use.
- A browser timer is a user interface feature. Server-side deadlines are also checked when saving or opening the exam, but a production system should run a server-side expiry job and handle expiry/submission atomically.
- One attempt per exam is enforced. Add retakes through an explicit attempt policy if required.
- Results use objective MCQs only; subjective answer marking is not implemented.
- The sample pass/fail rule is not hard-coded; staff can interpret scores or add a configurable pass threshold.
