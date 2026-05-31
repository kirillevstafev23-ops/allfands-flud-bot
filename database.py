import sqlite3

conn = sqlite3.connect("flud.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    role TEXT,
    fandom TEXT,
    status TEXT
)
""")

conn.commit()
conn.close()