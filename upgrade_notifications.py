import sqlite3

DATABASE = "database.db"

print("Starting Notification Center database upgrade...")
print("-----------------------------------------------")

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_notifications_user
    ON notifications(user_id)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_notifications_read
    ON notifications(user_id, is_read)
""")

conn.commit()
conn.close()

print("Notification Center upgrade complete!")
print("-----------------------------------------------")
print("Added:")
print("- Notifications table")
print("- Read / unread notification support")
print("- Notification types")
print("- Notification database indexes")