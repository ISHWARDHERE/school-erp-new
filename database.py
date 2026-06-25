import mysql.connector

def connect_db():
    conn = mysql.connector.connect(
        host="proxy.rlwy.net",
        user="root",
        password="rtWhYEPElwzIYDTTFkYgUZxxAcBZekLq",
        database="railway",
        port=57454
    )
    return conn

    except Exception as e:
        print("Database Error:", e)
        return None
