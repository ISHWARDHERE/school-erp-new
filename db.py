import sqlite3

def connect_db():
    conn = sqlite3.connect("school.db")
    conn.row_factory = sqlite3.Row
    return conn