import sqlite3

DB_NAME = "database.db"

conn = sqlite3.connect(DB_NAME)
cursor = conn.cursor()

print("=" * 55)
print("SMARTFINANCE AUTHENTICATION UPGRADE")
print("=" * 55)

columns = [
    ("email", "TEXT"),
    ("reset_otp", "TEXT"),
    ("reset_otp_expiry", "TEXT")
]

existing = [
    row[1]
    for row in cursor.execute("PRAGMA table_info(users)").fetchall()
]

for column, column_type in columns:
    if column not in existing:
        cursor.execute(
            f"ALTER TABLE users ADD COLUMN {column} {column_type}"
        )
        print(f"Added: {column}")
    else:
        print(f"Already exists: {column}")

cursor.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS
idx_users_email
ON users(email)
WHERE email IS NOT NULL
""")

conn.commit()
conn.close()

print()
print("AUTHENTICATION UPGRADE COMPLETE")
print("- Email accounts")
print("- Forgot Password")
print("- Email OTP recovery")
print("- OTP expiry support")
print("=" * 55)