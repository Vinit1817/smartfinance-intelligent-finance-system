from flask import Flask, render_template, request, redirect, session, Response, send_file
import psycopg2
from psycopg2.extras import RealDictCursor
import re
import math
import calendar
import os
import random
import smtplib
from datetime import datetime, date, timedelta
from email.message import EmailMessage
from io import BytesIO
import csv
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "smart-finance-secret-key"

DATABASE_URL = os.environ.get("DATABASE_URL", "")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
OTP_EXPIRY_MINUTES = 10

DEFAULT_CATEGORIES = [
    "Food",
    "Travel",
    "Shopping",
    "Bills",
    "Health",
    "Education",
    "Entertainment",
    "Other"
]


class DatabaseConnection:
    def __init__(self):
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not configured.")
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)

    @staticmethod
    def _sql(query):
        return query.replace("?", "%s").replace(
            "INSERT OR IGNORE INTO", "INSERT INTO"
        )

    def execute(self, query, params=()):
        sql = self._sql(query)
        if "INSERT INTO categories" in sql and "ON CONFLICT" not in sql:
            sql += " ON CONFLICT (user_id, name) DO NOTHING"
        self.cursor.execute(sql, params)
        return self.cursor

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.cursor.close()
        self.conn.close()


def get_db():
    return DatabaseConnection()


def init_db():
    conn = get_db()

    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            theme TEXT DEFAULT 'light',
            role TEXT DEFAULT 'user'
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower
        ON users (LOWER(email))
        WHERE email IS NOT NULL
        """,
        """
        CREATE TABLE IF NOT EXISTS monthly_income (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            UNIQUE(user_id, month)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS monthly_budgets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            UNIQUE(user_id, month)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            note TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS category_budgets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            category TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, month, category)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS savings_goals (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            target_amount DOUBLE PRECISION NOT NULL,
            saved_amount DOUBLE PRECISION DEFAULT 0,
            deadline TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS goal_contributions (
            id SERIAL PRIMARY KEY,
            goal_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            contribution_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'info',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS recurring_expenses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            category TEXT NOT NULL,
            day_of_month INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS recurring_expense_runs (
            id SERIAL PRIMARY KEY,
            recurring_expense_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            transaction_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(recurring_expense_id, month)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS bill_reminders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            due_date TEXT NOT NULL,
            category TEXT DEFAULT 'Bills',
            remind_days_before INTEGER DEFAULT 3,
            is_paid INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS password_reset_otps (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            otp TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_notifications_user
        ON notifications(user_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_notifications_read
        ON notifications(user_id, is_read)
        """
    ]

    for statement in statements:
        conn.execute(statement)

    conn.commit()
    conn.close()


def add_default_categories(user_id):
    conn = get_db()

    for category in DEFAULT_CATEGORIES:
        conn.execute("""
            INSERT OR IGNORE INTO categories (user_id, name)
            VALUES (?, ?)
        """, (user_id, category))

    conn.commit()
    conn.close()



def create_notification(conn, user_id, title, message,
                        notification_type="info"):
    existing = conn.execute("""
        SELECT id
        FROM notifications
        WHERE user_id = ?
        AND title = ?
        AND message = ?
    """, (user_id, title, message)).fetchone()

    if not existing:
        conn.execute("""
            INSERT INTO notifications
            (user_id, title, message, notification_type)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            title,
            message,
            notification_type
        ))


def generate_budget_notifications(conn, user_id, month):
    budget_row = conn.execute("""
        SELECT amount
        FROM monthly_budgets
        WHERE user_id = ? AND month = ?
    """, (user_id, month)).fetchone()

    spent = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE user_id = ?
        AND substr(date, 1, 7) = ?
    """, (user_id, month)).fetchone()[0]

    if budget_row and budget_row["amount"] > 0:
        budget = budget_row["amount"]
        percentage = (spent / budget) * 100

        if percentage >= 100:
            create_notification(
                conn,
                user_id,
                "Monthly Budget Exceeded",
                f"You have spent ₹{spent:.2f} against your "
                f"₹{budget:.2f} budget for {month}.",
                "danger"
            )
        elif percentage >= 80:
            create_notification(
                conn,
                user_id,
                "Monthly Budget Warning",
                f"You have used {percentage:.1f}% of your "
                f"monthly budget for {month}.",
                "warning"
            )

    category_rows = conn.execute("""
        SELECT
            cb.category,
            cb.amount AS budget,
            COALESCE(SUM(t.amount), 0) AS spent
        FROM category_budgets cb
        LEFT JOIN transactions t
            ON t.user_id = cb.user_id
            AND LOWER(t.category) = LOWER(cb.category)
            AND substr(t.date, 1, 7) = cb.month
        WHERE cb.user_id = ?
        AND cb.month = ?
        GROUP BY cb.id, cb.category, cb.amount
    """, (user_id, month)).fetchall()

    for row in category_rows:
        if row["budget"] <= 0:
            continue

        percentage = (row["spent"] / row["budget"]) * 100

        if percentage >= 100:
            create_notification(
                conn,
                user_id,
                f'{row["category"]} Budget Exceeded',
                f'{row["category"]} spending reached '
                f'₹{row["spent"]:.2f} against a '
                f'₹{row["budget"]:.2f} limit for {month}.',
                "danger"
            )
        elif percentage >= 80:
            create_notification(
                conn,
                user_id,
                f'{row["category"]} Budget Warning',
                f'{row["category"]} has used '
                f'{percentage:.1f}% of its budget for {month}.',
                "warning"
            )


def process_recurring_expenses(conn, user_id, target_month=None):
    if target_month is None:
        target_month = datetime.now().strftime("%Y-%m")

    try:
        target_date = datetime.strptime(target_month, "%Y-%m")
    except ValueError:
        return

    last_day = calendar.monthrange(
        target_date.year, target_date.month
    )[1]

    rows = conn.execute("""
        SELECT *
        FROM recurring_expenses
        WHERE user_id = ? AND is_active = 1
        AND substr(start_date, 1, 7) <= ?
    """, (user_id, target_month)).fetchall()

    for row in rows:
        already_run = conn.execute("""
            SELECT id FROM recurring_expense_runs
            WHERE recurring_expense_id = ? AND month = ?
        """, (row["id"], target_month)).fetchone()

        if already_run:
            continue

        expense_day = min(row["day_of_month"], last_day)
        expense_date = (
            f"{target_date.year:04d}-{target_date.month:02d}-"
            f"{expense_day:02d}"
        )

        cursor = conn.execute("""
            INSERT INTO transactions
            (user_id, amount, category, date, note)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id
        """, (
            user_id,
            row["amount"],
            row["category"],
            expense_date,
            f'Recurring: {row["title"]}'
        ))
        transaction_id = cursor.fetchone()["id"]

        conn.execute("""
            INSERT INTO recurring_expense_runs
            (recurring_expense_id, user_id, month, transaction_id)
            VALUES (?, ?, ?, ?)
        """, (
            row["id"], user_id, target_month, transaction_id
        ))

        create_notification(
            conn,
            user_id,
            "Recurring Expense Added",
            f'{row["title"]} ₹{row["amount"]:.2f} was recorded '
            f'for {target_month}.',
            "info"
        )


def generate_bill_notifications(conn, user_id):
    today = date.today()

    rows = conn.execute("""
        SELECT *
        FROM bill_reminders
        WHERE user_id = ? AND is_paid = 0
        ORDER BY due_date
    """, (user_id,)).fetchall()

    for row in rows:
        try:
            due_date = datetime.strptime(
                row["due_date"], "%Y-%m-%d"
            ).date()
        except ValueError:
            continue

        days_left = (due_date - today).days

        if days_left < 0:
            create_notification(
                conn,
                user_id,
                f'Bill Overdue: {row["title"]}',
                f'₹{row["amount"]:.2f} was due on {row["due_date"]}.',
                "danger"
            )
        elif days_left <= row["remind_days_before"]:
            if days_left == 0:
                message = (
                    f'₹{row["amount"]:.2f} is due today.'
                )
            elif days_left == 1:
                message = (
                    f'₹{row["amount"]:.2f} is due tomorrow.'
                )
            else:
                message = (
                    f'₹{row["amount"]:.2f} is due in '
                    f'{days_left} days.'
                )

            create_notification(
                conn,
                user_id,
                f'Bill Reminder: {row["title"]}',
                message,
                "warning"
            )


def calculate_financial_forecast(conn, user_id):
    current = date.today()
    history = []

    for offset in range(1, 4):
        month_number = current.month - offset
        year_number = current.year

        while month_number <= 0:
            month_number += 12
            year_number -= 1

        month_key = f"{year_number:04d}-{month_number:02d}"

        spent = conn.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = ? AND substr(date, 1, 7) = ?
        """, (user_id, month_key)).fetchone()[0]

        if spent > 0:
            history.append(float(spent))

    if history:
        predicted_expenses = round(sum(history) / len(history), 2)
    else:
        predicted_expenses = 0

    income_rows = conn.execute("""
        SELECT amount
        FROM monthly_income
        WHERE user_id = ?
        ORDER BY month DESC
        LIMIT 3
    """, (user_id,)).fetchall()

    incomes = [
        float(row["amount"])
        for row in income_rows
        if row["amount"] > 0
    ]

    predicted_income = (
        round(sum(incomes) / len(incomes), 2)
        if incomes else 0
    )

    predicted_savings = round(
        predicted_income - predicted_expenses, 2
    )

    if predicted_income <= 0:
        forecast_status = "Add income data to improve forecasting."
    elif predicted_savings > 0:
        forecast_status = (
            "Forecast indicates positive savings next month."
        )
    elif predicted_savings < 0:
        forecast_status = (
            "Forecast indicates expenses may exceed income next month."
        )
    else:
        forecast_status = "Forecast indicates a break-even month."

    return {
        "predicted_income": predicted_income,
        "predicted_expenses": predicted_expenses,
        "predicted_savings": predicted_savings,
        "forecast_status": forecast_status,
        "history_months": len(history)
    }


def validate_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def send_otp_email(recipient, otp):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise RuntimeError("SMTP email settings are not configured.")

    message = EmailMessage()
    message["Subject"] = "SmartFinance Password Reset OTP"
    message["From"] = SMTP_EMAIL
    message["To"] = recipient
    message.set_content(
        f"Your SmartFinance password reset OTP is {otp}. "
        f"It expires in {OTP_EXPIRY_MINUTES} minutes. "
        "Do not share this OTP."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(message)


def validate_password(password):
    return (
        len(password) >= 8
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"[0-9]", password)
    )


def previous_months(selected_month, count=6):
    selected_date = datetime.strptime(
        selected_month,
        "%Y-%m"
    )

    months = []

    year = selected_date.year
    month = selected_date.month

    for _ in range(count):
        months.append(f"{year:04d}-{month:02d}")

        month -= 1

        if month == 0:
            month = 12
            year -= 1

    months.reverse()

    return months


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        name = request.form["name"].strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form["password"]

        if len(name) < 3:
            error = "Username must contain at least 3 characters."
        elif not re.match(r"^[a-zA-Z0-9_]+$", name):
            error = "Username can only contain letters, numbers and underscore."
        elif not validate_email(email):
            error = "Enter a valid email address."
        elif not validate_password(password):
            error = (
                "Password must contain at least 8 characters, "
                "1 uppercase letter, 1 lowercase letter and 1 number."
            )
        else:
            conn = get_db()
            user = conn.execute("""
                SELECT id FROM users
                WHERE name = ? OR LOWER(email) = ?
            """, (name, email)).fetchone()

            if user:
                error = "Username or email already registered."
                conn.close()
            else:
                cursor = conn.execute("""
                    INSERT INTO users (name, email, password)
                    VALUES (?, ?, ?)
                    RETURNING id
                """, (name, email, generate_password_hash(password)))
                user_id = cursor.fetchone()["id"]
                conn.commit()
                conn.close()
                add_default_categories(user_id)
                return redirect("/login?registered=1")

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    success = None

    if request.args.get("registered") == "1":
        success = (
            "Account created successfully. "
            "You can now login."
        )
    elif request.args.get("reset") == "1":
        success = "Password reset successfully. You can now login."

    if request.method == "POST":
        name = request.form["name"].strip().lower()
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE name = ?
        """, (name,)).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            add_default_categories(user["id"])

            return redirect("/dashboard")

        error = "Invalid username or password."

    return render_template(
        "login.html",
        error=error,
        success=success
    )


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not validate_email(email):
            error = "Enter a valid email address."
        else:
            conn = get_db()
            user = conn.execute(
                "SELECT id, email FROM users WHERE LOWER(email) = ?",
                (email,)
            ).fetchone()

            if not user:
                conn.close()
                error = "No account is registered with this email."
            else:
                otp = f"{random.SystemRandom().randint(0, 999999):06d}"
                expires_at = (
                    datetime.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)
                ).strftime("%Y-%m-%d %H:%M:%S")

                conn.execute("""
                    UPDATE password_reset_otps
                    SET is_used = 1
                    WHERE user_id = ? AND is_used = 0
                """, (user["id"],))

                cursor = conn.execute("""
                    INSERT INTO password_reset_otps
                    (user_id, otp, expires_at)
                    VALUES (?, ?, ?)
                    RETURNING id
                """, (user["id"], otp, expires_at))
                otp_id = cursor.fetchone()["id"]
                conn.commit()

                try:
                    send_otp_email(user["email"], otp)
                except Exception as exc:
                    conn.execute(
                        "UPDATE password_reset_otps SET is_used = 1 WHERE id = ?",
                        (otp_id,)
                    )
                    conn.commit()
                    conn.close()
                    error = f"OTP email could not be sent: {exc}"
                else:
                    conn.close()
                    session["reset_user_id"] = user["id"]
                    session.pop("reset_otp_verified", None)
                    session.pop("reset_otp_id", None)
                    return redirect("/verify-otp")

    return render_template("forgot_password.html", error=error)


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    user_id = session.get("reset_user_id")
    if not user_id:
        return redirect("/forgot-password")

    error = None

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        conn = get_db()
        otp_row = conn.execute("""
            SELECT * FROM password_reset_otps
            WHERE user_id = ? AND otp = ? AND is_used = 0
            ORDER BY id DESC LIMIT 1
        """, (user_id, otp)).fetchone()

        if not otp_row:
            error = "Invalid OTP."
        else:
            expires_at = datetime.strptime(
                otp_row["expires_at"], "%Y-%m-%d %H:%M:%S"
            )

            if datetime.now() > expires_at:
                conn.execute(
                    "UPDATE password_reset_otps SET is_used = 1 WHERE id = ?",
                    (otp_row["id"],)
                )
                conn.commit()
                error = "OTP expired. Request a new OTP."
            else:
                session["reset_otp_verified"] = True
                session["reset_otp_id"] = otp_row["id"]
                conn.close()
                return redirect("/reset-password")

        conn.close()

    return render_template("verify_otp.html", error=error)


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    user_id = session.get("reset_user_id")
    otp_id = session.get("reset_otp_id")

    if not user_id or not otp_id or not session.get("reset_otp_verified"):
        return redirect("/forgot-password")

    error = None

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not validate_password(password):
            error = (
                "Password must contain at least 8 characters, "
                "1 uppercase letter, 1 lowercase letter and 1 number."
            )
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            conn = get_db()
            otp_row = conn.execute("""
                SELECT id FROM password_reset_otps
                WHERE id = ? AND user_id = ? AND is_used = 0
            """, (otp_id, user_id)).fetchone()

            if not otp_row:
                conn.close()
                session.pop("reset_user_id", None)
                session.pop("reset_otp_id", None)
                session.pop("reset_otp_verified", None)
                return redirect("/forgot-password")

            conn.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(password), user_id)
            )
            conn.execute(
                "UPDATE password_reset_otps SET is_used = 1 WHERE id = ?",
                (otp_id,)
            )
            conn.commit()
            conn.close()

            session.pop("reset_user_id", None)
            session.pop("reset_otp_id", None)
            session.pop("reset_otp_verified", None)
            return redirect("/login?reset=1")

    return render_template("reset_password.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    current_month = datetime.now().strftime("%Y-%m")
    month_number = request.args.get("month_number", "").strip()
    year = request.args.get("year", "").strip()
    legacy_month = request.args.get("month", "").strip()

    if month_number and year:
        try:
            year_number = int(year)
            month_value = int(month_number)

            if year_number < 1 or year_number > 9999:
                raise ValueError

            if month_value < 1 or month_value > 12:
                raise ValueError

            selected_month = f"{year_number:04d}-{month_value:02d}"

        except ValueError:
            selected_month = current_month

    elif re.fullmatch(r"\\d{4}-\\d{2}", legacy_month):
        selected_month = legacy_month

    else:
        selected_month = current_month

    selected_year = selected_month[:4]
    selected_month_number = selected_month[5:7]

    conn = get_db()

    process_recurring_expenses(conn, user_id, selected_month)
    generate_bill_notifications(conn, user_id)

    generate_budget_notifications(
        conn,
        user_id,
        selected_month
    )
    conn.commit()

    unread_notifications = conn.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id = ?
        AND is_read = 0
    """, (user_id,)).fetchone()[0]

    income_row = conn.execute("""
        SELECT amount
        FROM monthly_income
        WHERE user_id = ?
        AND month = ?
    """, (
        user_id,
        selected_month
    )).fetchone()

    income = income_row["amount"] if income_row else 0

    budget_row = conn.execute("""
        SELECT amount
        FROM monthly_budgets
        WHERE user_id = ?
        AND month = ?
    """, (
        user_id,
        selected_month
    )).fetchone()

    monthly_budget = (
        budget_row["amount"]
        if budget_row else 0
    )

    expenses = conn.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transactions
        WHERE user_id = ?
        AND substr(date, 1, 7) = ?
    """, (
        user_id,
        selected_month
    )).fetchone()[0]

    available_balance = income - expenses
    remaining_budget = monthly_budget - expenses

    budget_percentage = 0

    if monthly_budget > 0:
        budget_percentage = round(
            (expenses / monthly_budget) * 100,
            1
        )

    savings_rate = 0

    if income > 0:
        savings_rate = round(
            (available_balance / income) * 100,
            1
        )

    transactions = conn.execute("""
        SELECT *
        FROM transactions
        WHERE user_id = ?
        AND substr(date, 1, 7) = ?
        ORDER BY date DESC, id DESC
    """, (
        user_id,
        selected_month
    )).fetchall()

    category_data = conn.execute("""
        SELECT
            category,
            SUM(amount) AS total
        FROM transactions
        WHERE user_id = ?
        AND substr(date, 1, 7) = ?
        GROUP BY category
        ORDER BY total DESC
    """, (
        user_id,
        selected_month
    )).fetchall()

    chart_labels = [
        row["category"]
        for row in category_data
    ]

    chart_values = [
        row["total"]
        for row in category_data
    ]

    category_budget_rows = conn.execute("""
        SELECT
            cb.category,
            cb.amount AS budget,
            COALESCE(SUM(t.amount), 0) AS spent
        FROM category_budgets cb
        LEFT JOIN transactions t
            ON t.user_id = cb.user_id
            AND LOWER(t.category) = LOWER(cb.category)
            AND substr(t.date, 1, 7) = cb.month
        WHERE cb.user_id = ?
        AND cb.month = ?
        GROUP BY
            cb.id,
            cb.category,
            cb.amount
        ORDER BY cb.category
    """, (
        user_id,
        selected_month
    )).fetchall()

    category_budgets = []

    for row in category_budget_rows:
        budget_amount = row["budget"]
        spent = row["spent"]

        percentage = 0

        if budget_amount > 0:
            percentage = round(
                (spent / budget_amount) * 100,
                1
            )

        category_budgets.append({
            "category": row["category"],
            "budget": budget_amount,
            "spent": spent,
            "remaining": budget_amount - spent,
            "percentage": percentage
        })

    goal_rows = conn.execute("""
        SELECT *
        FROM savings_goals
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,)).fetchall()

    dashboard_goals = []

    total_goal_target = 0
    total_goal_saved = 0

    for goal in goal_rows:
        target = goal["target_amount"]
        saved = goal["saved_amount"]

        total_goal_target += target
        total_goal_saved += saved

        percentage = 0

        if target > 0:
            percentage = round(
                (saved / target) * 100,
                1
            )

        dashboard_goals.append({
            "id": goal["id"],
            "title": goal["title"],
            "target_amount": target,
            "saved_amount": saved,
            "remaining": max(target - saved, 0),
            "percentage": min(percentage, 100)
        })

    # ==================================================
    # FINANCIAL HEALTH SCORE
    # ==================================================

    savings_score = 0
    budget_score = 0
    spending_score = 0
    goal_score = 0

    if income > 0:
        if savings_rate >= 50:
            savings_score = 40
        elif savings_rate >= 30:
            savings_score = 35
        elif savings_rate >= 20:
            savings_score = 30
        elif savings_rate >= 10:
            savings_score = 20
        elif savings_rate > 0:
            savings_score = 10

    if monthly_budget > 0:
        if budget_percentage <= 50:
            budget_score = 30
        elif budget_percentage <= 70:
            budget_score = 25
        elif budget_percentage <= 80:
            budget_score = 20
        elif budget_percentage <= 100:
            budget_score = 10

    if income > 0:
        expense_ratio = (
            expenses / income
        ) * 100

        if expense_ratio <= 30:
            spending_score = 20
        elif expense_ratio <= 50:
            spending_score = 16
        elif expense_ratio <= 70:
            spending_score = 12
        elif expense_ratio <= 90:
            spending_score = 6

    goal_progress = 0

    if total_goal_target > 0:
        goal_progress = (
            total_goal_saved
            / total_goal_target
        ) * 100

        if goal_progress >= 75:
            goal_score = 10
        elif goal_progress >= 50:
            goal_score = 8
        elif goal_progress >= 25:
            goal_score = 6
        elif goal_progress > 0:
            goal_score = 3

    health_score = (
        savings_score
        + budget_score
        + spending_score
        + goal_score
    )

    if health_score >= 85:
        health_status = "Excellent"
        health_message = (
            "Your financial habits are performing "
            "at an excellent level."
        )

    elif health_score >= 70:
        health_status = "Good"
        health_message = (
            "Your finances are healthy with "
            "some room for improvement."
        )

    elif health_score >= 50:
        health_status = "Fair"
        health_message = (
            "Your finances are stable, but spending "
            "and savings need attention."
        )

    elif health_score >= 30:
        health_status = "Needs Attention"
        health_message = (
            "Your financial habits need better "
            "budget and savings control."
        )

    else:
        health_status = "Critical"
        health_message = (
            "Your current financial position "
            "requires immediate attention."
        )

    # ==================================================
    # 6 MONTH FINANCIAL INTELLIGENCE
    # ==================================================

    six_month_keys = previous_months(
        selected_month,
        6
    )

    six_month_labels = []
    six_month_expenses = []
    six_month_income = []
    six_month_savings = []

    month_performance = []

    for month_key in six_month_keys:
        month_date = datetime.strptime(
            month_key,
            "%Y-%m"
        )

        month_label = month_date.strftime("%b")

        month_expense = conn.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = ?
            AND substr(date, 1, 7) = ?
        """, (
            user_id,
            month_key
        )).fetchone()[0]

        month_income_row = conn.execute("""
            SELECT amount
            FROM monthly_income
            WHERE user_id = ?
            AND month = ?
        """, (
            user_id,
            month_key
        )).fetchone()

        month_income = (
            month_income_row["amount"]
            if month_income_row else 0
        )

        month_saving = (
            month_income - month_expense
        )

        six_month_labels.append(month_label)

        six_month_expenses.append(
            round(month_expense, 2)
        )

        six_month_income.append(
            round(month_income, 2)
        )

        six_month_savings.append(
            round(month_saving, 2)
        )

        month_performance.append({
            "key": month_key,
            "label": month_date.strftime(
                "%B %Y"
            ),
            "expense": month_expense,
            "income": month_income,
            "saving": month_saving
        })

    total_six_month_expenses = sum(
        six_month_expenses
    )

    average_monthly_spending = round(
        total_six_month_expenses
        / len(six_month_expenses),
        2
    )

    months_with_expenses = [
        month
        for month in month_performance
        if month["expense"] > 0
    ]

    if months_with_expenses:
        best_month_data = min(
            months_with_expenses,
            key=lambda item: item["expense"]
        )

        highest_month_data = max(
            months_with_expenses,
            key=lambda item: item["expense"]
        )

        best_spending_month = (
            best_month_data["label"]
        )

        highest_spending_month = (
            highest_month_data["label"]
        )

    else:
        best_spending_month = "No data"
        highest_spending_month = "No data"

    current_month_expense = (
        six_month_expenses[-1]
    )

    previous_month_expense = (
        six_month_expenses[-2]
        if len(six_month_expenses) >= 2
        else 0
    )

    spending_change = 0
    spending_change_status = "neutral"

    if previous_month_expense > 0:
        spending_change = round(
            (
                (
                    current_month_expense
                    - previous_month_expense
                )
                / previous_month_expense
            ) * 100,
            1
        )

        if spending_change < 0:
            spending_change_status = "down"

        elif spending_change > 0:
            spending_change_status = "up"

    elif current_month_expense > 0:
        spending_change_status = "new"

    current_saving = six_month_savings[-1]

    previous_saving = (
        six_month_savings[-2]
        if len(six_month_savings) >= 2
        else 0
    )

    if current_saving > previous_saving:
        savings_trend = "Improving"
    elif current_saving < previous_saving:
        savings_trend = "Declining"
    else:
        savings_trend = "Stable"

    trend_insights = []

    if spending_change_status == "down":
        trend_insights.append(
            f"Your spending decreased by "
            f"{abs(spending_change)}% compared "
            f"with last month."
        )

    elif spending_change_status == "up":
        trend_insights.append(
            f"Your spending increased by "
            f"{spending_change}% compared "
            f"with last month."
        )

    elif spending_change_status == "new":
        trend_insights.append(
            "No previous-month expense data is "
            "available for comparison."
        )

    else:
        trend_insights.append(
            "Your spending remained stable "
            "compared with last month."
        )

    if savings_trend == "Improving":
        trend_insights.append(
            "Your monthly savings performance "
            "is improving."
        )

    elif savings_trend == "Declining":
        trend_insights.append(
            "Your monthly savings have declined "
            "compared with last month."
        )

    else:
        trend_insights.append(
            "Your monthly savings trend is stable."
        )

    if current_month_expense < average_monthly_spending:
        trend_insights.append(
            "Current spending is below your "
            "six-month monthly average."
        )

    elif current_month_expense > average_monthly_spending:
        trend_insights.append(
            "Current spending is above your "
            "six-month monthly average."
        )

    # ==================================================
    # SMART INSIGHTS
    # ==================================================

    insights = []

    if category_data:
        highest = category_data[0]

        insights.append(
            f'Highest spending is '
            f'{highest["category"]} at '
            f'₹{highest["total"]:.2f}.'
        )

    if savings_rate >= 50:
        insights.append(
            "Your savings performance is excellent."
        )

    elif income > 0 and savings_rate < 20:
        insights.append(
            "Try to increase your monthly savings rate."
        )

    if budget_percentage > 100:
        insights.append(
            "Your monthly budget has been exceeded."
        )

    elif (
        monthly_budget > 0
        and budget_percentage <= 70
    ):
        insights.append(
            "Your monthly budget usage is under control."
        )

    if total_goal_target > 0:
        insights.append(
            f"Overall savings goal progress is "
            f"{round(goal_progress, 1)}%."
        )

    forecast = calculate_financial_forecast(conn, user_id)

    conn.commit()
    conn.close()

    return render_template(
        "dashboard.html",
        name=session["user_name"],
        selected_month=selected_month,
        selected_year=selected_year,
        selected_month_number=selected_month_number,
        income=income,
        monthly_budget=monthly_budget,
        expenses=expenses,
        remaining_budget=remaining_budget,
        available_balance=available_balance,
        budget_percentage=budget_percentage,
        savings_rate=savings_rate,
        transactions=transactions,
        chart_labels=chart_labels,
        chart_values=chart_values,
        category_budgets=category_budgets,
        dashboard_goals=dashboard_goals[:3],
        insights=insights,

        health_score=health_score,
        health_status=health_status,
        health_message=health_message,
        savings_score=savings_score,
        budget_score=budget_score,
        spending_score=spending_score,
        goal_score=goal_score,

        six_month_labels=six_month_labels,
        six_month_expenses=six_month_expenses,
        six_month_income=six_month_income,
        six_month_savings=six_month_savings,

        average_monthly_spending=average_monthly_spending,
        best_spending_month=best_spending_month,
        highest_spending_month=highest_spending_month,

        spending_change=spending_change,
        spending_change_status=spending_change_status,
        savings_trend=savings_trend,

        trend_insights=trend_insights,
        unread_notifications=unread_notifications,
        predicted_income=forecast["predicted_income"],
        predicted_expenses=forecast["predicted_expenses"],
        predicted_savings=forecast["predicted_savings"],
        forecast_status=forecast["forecast_status"],
        forecast_history_months=forecast["history_months"]
    )


@app.route("/income", methods=["GET", "POST"])
def income():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        month = request.form["month"]
        amount = float(request.form["amount"])

        conn = get_db()

        conn.execute("""
            INSERT INTO monthly_income
            (user_id, month, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, month)
            DO UPDATE SET amount = excluded.amount
        """, (
            session["user_id"],
            month,
            amount
        ))

        conn.commit()
        conn.close()

        return redirect(
            "/dashboard?month=" + month
        )

    return render_template("income.html")


@app.route("/budget", methods=["GET", "POST"])
def budget():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        month = request.form["month"]
        amount = float(request.form["amount"])

        conn = get_db()

        conn.execute("""
            INSERT INTO monthly_budgets
            (user_id, month, amount)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, month)
            DO UPDATE SET amount = excluded.amount
        """, (
            session["user_id"],
            month,
            amount
        ))

        conn.commit()
        conn.close()

        return redirect(
            "/dashboard?month=" + month
        )

    return render_template("budget.html")


@app.route(
    "/category-budgets",
    methods=["GET", "POST"]
)
def category_budgets():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    selected_month = request.args.get(
        "month",
        datetime.now().strftime("%Y-%m")
    )

    add_default_categories(user_id)

    conn = get_db()

    if request.method == "POST":
        month = request.form["month"]
        category = request.form["category"]
        amount = float(request.form["amount"])

        conn.execute("""
            INSERT INTO category_budgets
            (user_id, month, category, amount)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, month, category)
            DO UPDATE SET amount = excluded.amount
        """, (
            user_id,
            month,
            category,
            amount
        ))

        conn.commit()
        conn.close()

        return redirect(
            "/category-budgets?month=" + month
        )

    categories = conn.execute("""
        SELECT name
        FROM categories
        WHERE user_id = ?
        ORDER BY name
    """, (user_id,)).fetchall()

    budgets = conn.execute("""
        SELECT *
        FROM category_budgets
        WHERE user_id = ?
        AND month = ?
        ORDER BY category
    """, (
        user_id,
        selected_month
    )).fetchall()

    conn.close()

    return render_template(
        "category_budgets.html",
        categories=categories,
        budgets=budgets,
        selected_month=selected_month
    )


@app.route(
    "/add-expense",
    methods=["GET", "POST"]
)
def add_expense():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    add_default_categories(user_id)

    conn = get_db()

    if request.method == "POST":
        amount = float(request.form["amount"])
        category = request.form["category"]
        expense_date = request.form["date"]
        note = request.form["note"].strip()

        if amount <= 0:
            conn.close()
            return redirect("/add-expense")

        conn.execute("""
            INSERT INTO transactions
            (
                user_id,
                amount,
                category,
                date,
                note
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            amount,
            category,
            expense_date,
            note
        ))

        create_notification(
            conn,
            user_id,
            "Expense Recorded",
            f"₹{amount:.2f} was added under {category}.",
            "info"
        )

        generate_budget_notifications(
            conn,
            user_id,
            expense_date[:7]
        )

        conn.commit()
        conn.close()

        return redirect(
            "/dashboard?month="
            + expense_date[:7]
        )

    categories = conn.execute("""
        SELECT name
        FROM categories
        WHERE user_id = ?
        ORDER BY name
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "add_expense.html",
        categories=categories
    )


@app.route("/delete/<int:transaction_id>")
def delete_transaction(transaction_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    transaction = conn.execute("""
        SELECT date
        FROM transactions
        WHERE id = ?
        AND user_id = ?
    """, (
        transaction_id,
        session["user_id"]
    )).fetchone()

    if not transaction:
        conn.close()
        return redirect("/dashboard")

    month = transaction["date"][:7]

    conn.execute("""
        DELETE FROM transactions
        WHERE id = ?
        AND user_id = ?
    """, (
        transaction_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect(
        "/dashboard?month=" + month
    )


@app.route("/goals", methods=["GET", "POST"])
def goals():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    error = None

    conn = get_db()

    if request.method == "POST":
        title = request.form["title"].strip()

        try:
            target_amount = float(
                request.form["target_amount"]
            )
        except ValueError:
            target_amount = 0

        deadline = request.form["deadline"]

        if not title:
            error = "Goal name is required."

        elif target_amount <= 0:
            error = (
                "Target amount must be greater "
                "than zero."
            )

        else:
            try:
                deadline_date = datetime.strptime(
                    deadline,
                    "%Y-%m-%d"
                ).date()

                if deadline_date <= date.today():
                    error = (
                        "Goal deadline must be "
                        "a future date."
                    )

            except ValueError:
                error = "Invalid deadline."

        if not error:
            conn.execute("""
                INSERT INTO savings_goals
                (
                    user_id,
                    title,
                    target_amount,
                    saved_amount,
                    deadline
                )
                VALUES (?, ?, ?, 0, ?)
            """, (
                user_id,
                title,
                target_amount,
                deadline
            ))

            conn.commit()
            conn.close()

            return redirect("/goals")

    goal_rows = conn.execute("""
        SELECT *
        FROM savings_goals
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,)).fetchall()

    goals_data = []

    today = date.today()

    for goal in goal_rows:
        target = goal["target_amount"]
        saved = goal["saved_amount"]

        remaining = max(
            target - saved,
            0
        )

        percentage = 0

        if target > 0:
            percentage = round(
                (saved / target) * 100,
                1
            )

        percentage = min(
            percentage,
            100
        )

        months_remaining = 0
        monthly_required = 0

        if goal["deadline"]:
            deadline_date = datetime.strptime(
                goal["deadline"],
                "%Y-%m-%d"
            ).date()

            months_remaining = (
                (
                    deadline_date.year
                    - today.year
                ) * 12
                + deadline_date.month
                - today.month
            )

            if deadline_date.day > today.day:
                months_remaining += 1

            months_remaining = max(
                months_remaining,
                0
            )

            if months_remaining > 0:
                monthly_required = math.ceil(
                    remaining
                    / months_remaining
                )

        goals_data.append({
            "id": goal["id"],
            "title": goal["title"],
            "target_amount": target,
            "saved_amount": saved,
            "remaining": remaining,
            "percentage": percentage,
            "deadline": goal["deadline"],
            "months_remaining": months_remaining,
            "monthly_required": monthly_required
        })

    conn.close()

    return render_template(
        "goals.html",
        goals=goals_data,
        error=error
    )


@app.route(
    "/goals/<int:goal_id>/contribute",
    methods=["POST"]
)
def contribute_goal(goal_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    try:
        amount = float(
            request.form["amount"]
        )
    except ValueError:
        return redirect("/goals")

    if amount <= 0:
        return redirect("/goals")

    conn = get_db()

    goal = conn.execute("""
        SELECT *
        FROM savings_goals
        WHERE id = ?
        AND user_id = ?
    """, (
        goal_id,
        user_id
    )).fetchone()

    if not goal:
        conn.close()
        return redirect("/goals")

    remaining = max(
        goal["target_amount"]
        - goal["saved_amount"],
        0
    )

    contribution = min(
        amount,
        remaining
    )

    if contribution > 0:
        conn.execute("""
            INSERT INTO goal_contributions
            (
                goal_id,
                user_id,
                amount,
                contribution_date
            )
            VALUES (?, ?, ?, ?)
        """, (
            goal_id,
            user_id,
            contribution,
            date.today().isoformat()
        ))

        conn.execute("""
            UPDATE savings_goals
            SET saved_amount = saved_amount + ?
            WHERE id = ?
            AND user_id = ?
        """, (
            contribution,
            goal_id,
            user_id
        ))

        new_saved_amount = (
            goal["saved_amount"] + contribution
        )

        if new_saved_amount >= goal["target_amount"]:
            create_notification(
                conn,
                user_id,
                "Savings Goal Completed",
                f'Congratulations! Your "{goal["title"]}" '
                f'savings goal has been completed.',
                "success"
            )

        conn.commit()

    conn.close()

    return redirect("/goals")


@app.route(
    "/goals/<int:goal_id>/delete",
    methods=["POST"]
)
def delete_goal(goal_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db()

    conn.execute("""
        DELETE FROM goal_contributions
        WHERE goal_id = ?
        AND user_id = ?
    """, (
        goal_id,
        user_id
    ))

    conn.execute("""
        DELETE FROM savings_goals
        WHERE id = ?
        AND user_id = ?
    """, (
        goal_id,
        user_id
    ))

    conn.commit()
    conn.close()

    return redirect("/goals")



@app.route("/recurring-expenses", methods=["GET", "POST"])
def recurring_expenses():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    add_default_categories(user_id)
    error = None
    conn = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        start_date = request.form.get("start_date", "").strip()

        try:
            amount = float(request.form.get("amount", "0"))
            day_of_month = int(
                request.form.get("day_of_month", "1")
            )
        except ValueError:
            amount = 0
            day_of_month = 0

        if not title:
            error = "Expense name is required."
        elif amount <= 0:
            error = "Amount must be greater than zero."
        elif not category:
            error = "Category is required."
        elif day_of_month < 1 or day_of_month > 31:
            error = "Billing day must be between 1 and 31."
        else:
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                error = "Enter a valid start date."

        if not error:
            conn.execute("""
                INSERT INTO recurring_expenses
                (
                    user_id, title, amount, category,
                    day_of_month, start_date
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, title, amount, category,
                day_of_month, start_date
            ))
            conn.commit()
            conn.close()
            return redirect("/recurring-expenses")

    rows = conn.execute("""
        SELECT *
        FROM recurring_expenses
        WHERE user_id = ?
        ORDER BY is_active DESC, created_at DESC
    """, (user_id,)).fetchall()

    categories = conn.execute("""
        SELECT name FROM categories
        WHERE user_id = ?
        ORDER BY name
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "recurring_expenses.html",
        recurring_expenses=rows,
        categories=categories,
        error=error
    )


@app.route(
    "/recurring-expenses/<int:expense_id>/toggle",
    methods=["POST"]
)
def toggle_recurring_expense(expense_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    conn.execute("""
        UPDATE recurring_expenses
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE id = ? AND user_id = ?
    """, (expense_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/recurring-expenses")


@app.route(
    "/recurring-expenses/<int:expense_id>/delete",
    methods=["POST"]
)
def delete_recurring_expense(expense_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    conn.execute("""
        DELETE FROM recurring_expense_runs
        WHERE recurring_expense_id = ? AND user_id = ?
    """, (expense_id, session["user_id"]))
    conn.execute("""
        DELETE FROM recurring_expenses
        WHERE id = ? AND user_id = ?
    """, (expense_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/recurring-expenses")


@app.route("/bill-reminders", methods=["GET", "POST"])
def bill_reminders():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    error = None
    conn = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        due_date = request.form.get("due_date", "").strip()
        category = request.form.get("category", "Bills").strip()

        try:
            amount = float(request.form.get("amount", "0"))
            remind_days_before = int(
                request.form.get("remind_days_before", "3")
            )
        except ValueError:
            amount = 0
            remind_days_before = -1

        if not title:
            error = "Bill name is required."
        elif amount <= 0:
            error = "Amount must be greater than zero."
        elif remind_days_before < 0 or remind_days_before > 30:
            error = "Reminder days must be between 0 and 30."
        else:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                error = "Enter a valid due date."

        if not error:
            conn.execute("""
                INSERT INTO bill_reminders
                (
                    user_id, title, amount, due_date,
                    category, remind_days_before
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, title, amount, due_date,
                category, remind_days_before
            ))
            conn.commit()
            conn.close()
            return redirect("/bill-reminders")

    generate_bill_notifications(conn, user_id)
    conn.commit()

    rows = conn.execute("""
        SELECT *
        FROM bill_reminders
        WHERE user_id = ?
        ORDER BY is_paid, due_date
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "bill_reminders.html",
        bills=rows,
        error=error,
        today=date.today().isoformat()
    )


@app.route(
    "/bill-reminders/<int:bill_id>/paid",
    methods=["POST"]
)
def mark_bill_paid(bill_id):
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db()

    bill = conn.execute("""
        SELECT *
        FROM bill_reminders
        WHERE id = ? AND user_id = ?
    """, (bill_id, user_id)).fetchone()

    if bill and not bill["is_paid"]:
        conn.execute("""
            UPDATE bill_reminders
            SET is_paid = 1
            WHERE id = ? AND user_id = ?
        """, (bill_id, user_id))

        conn.execute("""
            INSERT INTO transactions
            (user_id, amount, category, date, note)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            bill["amount"],
            bill["category"],
            date.today().isoformat(),
            f'Bill paid: {bill["title"]}'
        ))

        create_notification(
            conn,
            user_id,
            "Bill Paid",
            f'{bill["title"]} ₹{bill["amount"]:.2f} '
            "was marked as paid and recorded as an expense.",
            "success"
        )
        conn.commit()

    conn.close()
    return redirect("/bill-reminders")


@app.route(
    "/bill-reminders/<int:bill_id>/delete",
    methods=["POST"]
)
def delete_bill_reminder(bill_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    conn.execute("""
        DELETE FROM bill_reminders
        WHERE id = ? AND user_id = ?
    """, (bill_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/bill-reminders")


@app.route("/forecast")
def financial_forecast():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    forecast = calculate_financial_forecast(
        conn, session["user_id"]
    )
    conn.close()

    return render_template(
        "forecast.html",
        **forecast
    )


@app.route("/notifications")
def notifications():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    notification_rows = conn.execute("""
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
    """, (session["user_id"],)).fetchall()

    unread_count = conn.execute("""
        SELECT COUNT(*)
        FROM notifications
        WHERE user_id = ?
        AND is_read = 0
    """, (session["user_id"],)).fetchone()[0]

    conn.close()

    return render_template(
        "notifications.html",
        notifications=notification_rows,
        unread_count=unread_count
    )


@app.route(
    "/notifications/<int:notification_id>/read",
    methods=["POST"]
)
def mark_notification_read(notification_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE id = ?
        AND user_id = ?
    """, (
        notification_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/notifications")


@app.route(
    "/notifications/read-all",
    methods=["POST"]
)
def mark_all_notifications_read():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ?
    """, (session["user_id"],))

    conn.commit()
    conn.close()

    return redirect("/notifications")


@app.route(
    "/notifications/<int:notification_id>/delete",
    methods=["POST"]
)
def delete_notification(notification_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        DELETE FROM notifications
        WHERE id = ?
        AND user_id = ?
    """, (
        notification_id,
        session["user_id"]
    ))

    conn.commit()
    conn.close()

    return redirect("/notifications")



@app.route("/expense/<int:transaction_id>/edit", methods=["GET", "POST"])
def edit_expense(transaction_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    expense = conn.execute("""
        SELECT *
        FROM transactions
        WHERE id = ? AND user_id = ?
    """, (transaction_id, session["user_id"])).fetchone()

    if not expense:
        conn.close()
        return redirect("/dashboard")

    categories = conn.execute("""
        SELECT name FROM categories
        WHERE user_id = ?
        ORDER BY name
    """, (session["user_id"],)).fetchall()

    error = None

    if request.method == "POST":
        try:
            amount = float(request.form["amount"])
        except ValueError:
            amount = 0

        category = request.form["category"].strip()
        expense_date = request.form["date"]
        note = request.form.get("note", "").strip()

        if amount <= 0:
            error = "Amount must be greater than zero."
        elif not category or not expense_date:
            error = "Category and date are required."
        else:
            conn.execute("""
                UPDATE transactions
                SET amount = ?, category = ?, date = ?, note = ?
                WHERE id = ? AND user_id = ?
            """, (
                amount, category, expense_date, note,
                transaction_id, session["user_id"]
            ))
            generate_budget_notifications(
                conn, session["user_id"], expense_date[:7]
            )
            conn.commit()
            conn.close()
            return redirect("/dashboard?month=" + expense_date[:7])

    conn.close()
    return render_template(
        "edit_expense.html",
        expense=expense,
        categories=categories,
        error=error
    )


@app.route("/expenses")
def expenses():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    from_date = request.args.get("from_date", request.args.get("start_date", "")).strip()
    to_date = request.args.get("to_date", request.args.get("end_date", "")).strip()
    min_amount = request.args.get("min_amount", "").strip()
    max_amount = request.args.get("max_amount", "").strip()

    filters = {
        "search": search,
        "category": category,
        "from_date": from_date,
        "to_date": to_date,
        "start_date": from_date,
        "end_date": to_date,
        "min_amount": min_amount,
        "max_amount": max_amount
    }

    query = "SELECT * FROM transactions WHERE user_id = ?"
    params = [user_id]

    if search:
        query += " AND (LOWER(COALESCE(note, '')) LIKE ? OR LOWER(category) LIKE ?)"
        search_value = f"%{search.lower()}%"
        params.extend([search_value, search_value])

    if category:
        query += " AND category = ?"
        params.append(category)

    if from_date:
        query += " AND date >= ?"
        params.append(from_date)

    if to_date:
        query += " AND date <= ?"
        params.append(to_date)

    if min_amount:
        try:
            query += " AND amount >= ?"
            params.append(float(min_amount))
        except ValueError:
            filters["min_amount"] = ""

    if max_amount:
        try:
            query += " AND amount <= ?"
            params.append(float(max_amount))
        except ValueError:
            filters["max_amount"] = ""

    query += " ORDER BY date DESC, id DESC"

    conn = get_db()
    rows = conn.execute(query, params).fetchall()

    categories = conn.execute("""
        SELECT name
        FROM categories
        WHERE user_id = ?
        ORDER BY name
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "expenses.html",
        expenses=rows,
        transactions=rows,
        categories=categories,
        filters=filters
    )


@app.route("/categories", methods=["GET", "POST"])
def categories():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    error = None
    conn = get_db()

    if request.method == "POST":
        name = request.form["name"].strip()

        if len(name) < 2:
            error = "Category name must contain at least 2 characters."
        else:
            existing = conn.execute("""
                SELECT id FROM categories
                WHERE user_id = ? AND LOWER(name) = LOWER(?)
            """, (user_id, name)).fetchone()

            if existing:
                error = "Category already exists."
            else:
                conn.execute("""
                    INSERT INTO categories (user_id, name)
                    VALUES (?, ?)
                """, (user_id, name))
                conn.commit()
                conn.close()
                return redirect("/categories")

    rows = conn.execute("""
        SELECT * FROM categories
        WHERE user_id = ?
        ORDER BY name
    """, (user_id,)).fetchall()
    conn.close()

    return render_template(
        "categories.html",
        categories=rows,
        default_categories=DEFAULT_CATEGORIES,
        error=error
    )


@app.route("/categories/<int:category_id>/delete", methods=["POST"])
def delete_category(category_id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    category = conn.execute("""
        SELECT * FROM categories
        WHERE id = ? AND user_id = ?
    """, (category_id, session["user_id"])).fetchone()

    if category and category["name"] not in DEFAULT_CATEGORIES:
        conn.execute("""
            DELETE FROM categories
            WHERE id = ? AND user_id = ?
        """, (category_id, session["user_id"]))
        conn.commit()

    conn.close()
    return redirect("/categories")


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    error = None
    success = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "username":
            new_name = request.form["name"].strip().lower()

            if len(new_name) < 3:
                error = "Username must contain at least 3 characters."
            elif not re.match(r"^[a-zA-Z0-9_]+$", new_name):
                error = "Username can only contain letters, numbers and underscore."
            else:
                taken = conn.execute("""
                    SELECT id FROM users
                    WHERE name = ? AND id != ?
                """, (new_name, user_id)).fetchone()

                if taken:
                    error = "Username already taken."
                else:
                    conn.execute(
                        "UPDATE users SET name = ? WHERE id = ?",
                        (new_name, user_id)
                    )
                    conn.commit()
                    session["user_name"] = new_name
                    success = "Username updated successfully."

        elif action == "password":
            current_password = request.form["current_password"]
            new_password = request.form["new_password"]

            if not check_password_hash(user["password"], current_password):
                error = "Current password is incorrect."
            elif not validate_password(new_password):
                error = (
                    "New password needs 8 characters, uppercase, "
                    "lowercase and a number."
                )
            else:
                conn.execute("""
                    UPDATE users SET password = ? WHERE id = ?
                """, (generate_password_hash(new_password), user_id))
                conn.commit()
                success = "Password changed successfully."

        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        error=error,
        success=success
    )


@app.route("/theme", methods=["POST"])
def update_theme():
    if "user_id" not in session:
        return {"ok": False}, 401

    theme = request.form.get("theme", "light")
    if theme not in ("light", "dark"):
        theme = "light"

    conn = get_db()
    conn.execute(
        "UPDATE users SET theme = ? WHERE id = ?",
        (theme, session["user_id"])
    )
    conn.commit()
    conn.close()
    session["theme"] = theme

    return {"ok": True, "theme": theme}


@app.route("/export/csv")
def export_csv():
    if "user_id" not in session:
        return redirect("/login")

    month = request.args.get(
        "month", datetime.now().strftime("%Y-%m")
    )

    conn = get_db()
    rows = conn.execute("""
        SELECT amount, category, date, note
        FROM transactions
        WHERE user_id = ? AND substr(date, 1, 7) = ?
        ORDER BY date DESC
    """, (session["user_id"], month)).fetchall()
    conn.close()

    output = BytesIO()
    text = output
    content = "Amount,Category,Date,Note\n"
    for row in rows:
        note = (row["note"] or "").replace('"', '""')
        content += (
            f'{row["amount"]},"{row["category"]}",'
            f'{row["date"]},"{note}"\n'
        )

    output.write(content.encode("utf-8-sig"))
    output.seek(0)

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"smartfinance_{month}.csv"
    )


@app.route("/export/pdf")
def export_pdf():
    if "user_id" not in session:
        return redirect("/login")

    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet

    month = request.args.get(
        "month", datetime.now().strftime("%Y-%m")
    )
    user_id = session["user_id"]

    conn = get_db()
    income_row = conn.execute("""
        SELECT amount FROM monthly_income
        WHERE user_id = ? AND month = ?
    """, (user_id, month)).fetchone()
    budget_row = conn.execute("""
        SELECT amount FROM monthly_budgets
        WHERE user_id = ? AND month = ?
    """, (user_id, month)).fetchone()
    rows = conn.execute("""
        SELECT amount, category, date, note
        FROM transactions
        WHERE user_id = ? AND substr(date, 1, 7) = ?
        ORDER BY date DESC
    """, (user_id, month)).fetchall()
    conn.close()

    income = income_row["amount"] if income_row else 0
    budget = budget_row["amount"] if budget_row else 0
    spent = sum(row["amount"] for row in rows)
    balance = income - spent

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SmartFinance Monthly Report", styles["Title"]),
        Paragraph(f"Month: {month}", styles["Normal"]),
        Spacer(1, 14),
        Table([
            ["Monthly Income", f"INR {income:.2f}"],
            ["Monthly Budget", f"INR {budget:.2f}"],
            ["Total Spent", f"INR {spent:.2f}"],
            ["Available Balance", f"INR {balance:.2f}"],
        ]),
        Spacer(1, 18),
        Paragraph("Expense History", styles["Heading2"])
    ]

    data = [["Amount", "Category", "Date", "Note"]]
    for row in rows:
        data.append([
            f"INR {row['amount']:.2f}",
            row["category"],
            row["date"],
            row["note"] or "-"
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    doc.build(story)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"smartfinance_{month}.pdf"
    )


def admin_required():
    if "user_id" not in session:
        return False

    conn = get_db()
    user = conn.execute(
        "SELECT is_admin FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()

    return bool(user and user["is_admin"] == 1)


@app.route("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect("/dashboard")

    conn = get_db()
    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]
    total_expenses = conn.execute(
        "SELECT COUNT(*) FROM transactions"
    ).fetchone()[0]
    total_value = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM transactions"
    ).fetchone()[0]
    users = conn.execute("""
        SELECT
            u.id,
            u.name,
            u.is_admin,
            u.created_at,
            COUNT(t.id) AS expense_count,
            COALESCE(SUM(t.amount), 0) AS expense_total
        FROM users u
        LEFT JOIN transactions t ON t.user_id = u.id
        GROUP BY u.id
        ORDER BY u.id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_expenses=total_expenses,
        total_value=total_value,
        users=users
    )


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
def admin_change_role(user_id):
    if not admin_required():
        return redirect("/dashboard")

    is_admin = 1 if request.form.get("role") == "admin" else 0

    conn = get_db()
    conn.execute(
        "UPDATE users SET is_admin = ? WHERE id = ?",
        (is_admin, user_id)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


@app.context_processor
def inject_global_ui():
    if "user_id" not in session:
        return {"current_theme": "light", "is_admin": False}

    conn = get_db()
    user = conn.execute("""
        SELECT theme, is_admin FROM users WHERE id = ?
    """, (session["user_id"],)).fetchone()
    conn.close()

    return {
        "current_theme": user["theme"] if user else "light",
        "is_admin": bool(user and user["is_admin"] == 1)
    }


@app.route("/logout")
def logout():
    session.clear()

    return redirect("/login")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)