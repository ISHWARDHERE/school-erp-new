import mysql.connector


def connect_db():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Radha@1437",
        database="school_online"
    )
    return conn