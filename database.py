import mysql.connector

def connect_db():
    try:
        conn = mysql.connector.connect(
            host="reseau.proxy.rlwy.net",
            user="root",
            password="rtWhYEPElwzIYDTTFkYgUZxxAcBZekLq",
            database="railway",
            port=57454
        )
        return conn

    except Exception as e:
        print("Database Error:", e)
        return None