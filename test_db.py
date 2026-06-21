import mysql.connector

try:
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Radha@1437",
        database="school_online"
    )

    print("MySQL Connected Successfully")

except Exception as e:
    print("DB Error:", e)