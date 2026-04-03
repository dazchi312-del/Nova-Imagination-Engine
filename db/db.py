import sqlite3

DB_PATH = "db/nova.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    with open("db/schema.sql", "r", encoding="utf-8") as f:
        schema = f.read()

    conn = get_connection()
    conn.executescript(schema)
    conn.commit()
    conn.close()
