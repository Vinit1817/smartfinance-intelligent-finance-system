import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

categories = [
    "Food",
    "Travel",
    "Shopping",
    "Bills",
    "Health",
    "Education",
    "Entertainment",
    "Other"
]

users = cursor.execute("SELECT id FROM users").fetchall()

for user in users:
    for category in categories:
        cursor.execute(
            """
            INSERT OR IGNORE INTO categories (user_id, name)
            VALUES (?, ?)
            """,
            (user[0], category)
        )

conn.commit()
conn.close()

print("Categories added successfully!")