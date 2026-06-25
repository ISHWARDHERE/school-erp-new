import os
import mysql.connector

def connect_db():
    try:
        host = os.getenv("DB_HOST")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")
        database = os.getenv("DB_NAME")
        port = int(os.getenv("DB_PORT"))

        print(host, user, database, port)

        conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            connection_timeout=10
        )

        print("Database Connected")
        return conn

    except Exception as e:
        print("Database Error:", str(e))
        return None