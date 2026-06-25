import mysql.connector

def connect_db():
    try:
        conn = mysql.connector.connect(
           host="MYSQLHOST",
           user="MYSQLUSER",
           password="MYSQLPASSWORD",
           database="MYSQLDATABASE",
           port=MYSQLPORT
        )

        if conn.is_connected():
            print("Database Connected")

        return conn

    except Exception as e:
        print("Database Error:", e)
        return None
