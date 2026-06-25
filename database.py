import mysql.connector

def connect_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="schooladmin",
            password="admin123",
            database="school_db",
            port=3306
        )

        if conn.is_connected():
            print("Database Connected")

        return conn

    except Exception as e:
        print("Database Error:", e)
        return None
