import os
import mysql.connector

def connect_db():
    try:
        db_port = int(os.getenv("DB_PORT"))

        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME"),
            port=db_port
        )

        print("Database Connected")
        return conn

    except Exception as e:
        print("Database Error:", e)
        return None
