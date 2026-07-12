import sqlite3

DB_NAME = "database.db"

print("=" * 60)
print("SMARTFINANCE ADVANCED FINANCE ENGINE UPGRADE")
print("=" * 60)

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

cursor.execute("PRAGMA foreign_keys = ON")


# =========================================================
# RECURRING EXPENSES
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    category TEXT NOT NULL,
    frequency TEXT NOT NULL,
    start_date TEXT NOT NULL,
    next_due_date TEXT NOT NULL,
    note TEXT,
    is_active INTEGER DEFAULT 1,
    last_generated_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id)
    REFERENCES users(id)
    ON DELETE CASCADE
)
""")


# =========================================================
# BILL REMINDERS
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS bill_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bill_name TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    category TEXT NOT NULL,
    due_date TEXT NOT NULL,
    note TEXT,
    status TEXT DEFAULT 'pending',
    reminder_days INTEGER DEFAULT 3,
    is_paid INTEGER DEFAULT 0,
    paid_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(user_id)
    REFERENCES users(id)
    ON DELETE CASCADE
)
""")


# =========================================================
# FORECAST CACHE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS financial_forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    forecast_month TEXT NOT NULL,
    predicted_expenses REAL DEFAULT 0,
    predicted_income REAL DEFAULT 0,
    predicted_savings REAL DEFAULT 0,
    confidence_score REAL DEFAULT 0,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, forecast_month),

    FOREIGN KEY(user_id)
    REFERENCES users(id)
    ON DELETE CASCADE
)
""")


# =========================================================
# FORECAST CATEGORY DATA
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS category_forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    forecast_month TEXT NOT NULL,
    category TEXT NOT NULL,
    predicted_amount REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(user_id, forecast_month, category),

    FOREIGN KEY(user_id)
    REFERENCES users(id)
    ON DELETE CASCADE
)
""")


# =========================================================
# DATABASE INDEXES
# =========================================================

cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_recurring_user_due
ON recurring_expenses(user_id, next_due_date)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_recurring_user_active
ON recurring_expenses(user_id, is_active)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_bills_user_due
ON bill_reminders(user_id, due_date)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_bills_user_paid
ON bill_reminders(user_id, is_paid)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_forecast_user_month
ON financial_forecasts(user_id, forecast_month)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS
idx_category_forecast_user_month
ON category_forecasts(user_id, forecast_month)
""")


conn.commit()
conn.close()

print()
print("DATABASE UPGRADE COMPLETE")
print()
print("Added:")
print("- Recurring Expense Engine")
print("- Automatic Expense Scheduling")
print("- Bill Reminder System")
print("- Bill Payment Tracking")
print("- Financial Forecast Storage")
print("- Category Forecast Intelligence")
print("- Performance Indexes")
print()
print("=" * 60)
print("SMARTFINANCE ADVANCED ENGINE READY")
print("=" * 60)