import sqlite3

conn = sqlite3.connect("db/nova.db")
cur = conn.cursor()

cur.execute("DELETE FROM creative_sessions WHERE session_id = '1'")

conn.commit()
conn.close()

print("old test row removed")
