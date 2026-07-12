import sqlite3
from datetime import datetime

DATABASE = "database.db"


def table_exists(cursor, table):
    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
    """, (table,))
    return cursor.fetchone() is not None


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

cursor.execute("PRAGMA foreign_keys = ON")

print("=" * 55)
print("SMARTFINANCE PREMIUM DATABASE UPGRADE")
print("=" * 55)

if not table_exists(cursor, "users"):
    print("ERROR: users table not found.")
    print("Copy your original database.db into this project folder.")
    conn.close()
    raise SystemExit(1)


current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =====================================================
# USERS
# =====================================================

if not column_exists(cursor, "users", "created_at"):
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN created_at TEXT
    """)

cursor.execute("""
    UPDATE users
    SET created_at = ?
    WHERE created_at IS NULL
""", (current_time,))


if not column_exists(cursor, "users", "currency"):
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN currency TEXT DEFAULT 'INR'
    """)


if not column_exists(cursor, "users", "theme"):
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN theme TEXT DEFAULT 'light'
    """)


if not column_exists(cursor, "users", "is_admin"):
    cursor.execute("""
        ALTER TABLE users
        ADD COLUMN is_admin INTEGER DEFAULT 0
    """)


# =====================================================
# NOTIFICATIONS
# =====================================================

cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
    )
""")


# =====================================================
# CUSTOM CATEGORIES
# =====================================================

cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        UNIQUE(user_id, name),

        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
    )
""")


# =====================================================
# CATEGORY BUDGETS
# =====================================================

cursor.execute("""
    CREATE TABLE IF NOT EXISTS category_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount >= 0),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        UNIQUE(user_id, month, category),

        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
    )
""")


# =====================================================
# SAVINGS GOALS
# =====================================================

cursor.execute("""
    CREATE TABLE IF NOT EXISTS savings_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        target_amount REAL NOT NULL CHECK(target_amount > 0),
        saved_amount REAL DEFAULT 0 CHECK(saved_amount >= 0),
        deadline TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
    )
""")


# =====================================================
# GOAL CONTRIBUTIONS
# =====================================================

cursor.execute("""
    CREATE TABLE IF NOT EXISTS goal_contributions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        contribution_date TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,

        FOREIGN KEY(goal_id)
        REFERENCES savings_goals(id)
        ON DELETE CASCADE,

        FOREIGN KEY(user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
    )
""")


# =====================================================
# DEFAULT CATEGORIES
# =====================================================

default_categories = [
    "Food",
    "Travel",
    "Shopping",
    "Bills",
    "Health",
    "Education",
    "Entertainment",
    "Other"
]

users = cursor.execute("""
    SELECT id
    FROM users
""").fetchall()

for user in users:
    user_id = user[0]

    for category in default_categories:
        cursor.execute("""
            INSERT OR IGNORE INTO categories
            (user_id, name)
            VALUES (?, ?)
        """, (
            user_id,
            category
        ))


# =====================================================
# DATABASE INDEXES
# =====================================================

if table_exists(cursor, "transactions"):
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_transactions_user_date
        ON transactions(user_id, date)
    """)

cursor.execute("""
    CREATE INDEX IF NOT EXISTS
    idx_category_budgets_user_month
    ON category_budgets(user_id, month)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS
    idx_notifications_user_read
    ON notifications(user_id, is_read)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS
    idx_goals_user
    ON savings_goals(user_id)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS
    idx_categories_user
    ON categories(user_id)
""")


conn.commit()
conn.close()


print()
print("DATABASE UPGRADE COMPLETE")
print("- Premium user settings")
print("- Admin access system")
print("- Notification centre")
print("- Custom categories")
print("- Category budget control")
print("- Savings goal engine")
print("- Goal contributions")
print("- Performance indexes")
print("=" * 55)