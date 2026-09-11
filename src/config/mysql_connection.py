import pymysql

def get_mysql_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        db="mercancia",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )