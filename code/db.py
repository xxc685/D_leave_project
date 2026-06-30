import os
import pymysql
from pymysql.cursors import DictCursor

def get_conn():
    return pymysql.connect(
        host="localhost",
        port=3306,
        user="root",
        password=os.environ["MYSQL_PASSWORD"],        #填入本地 MySQL 的 root 密码
        database="attendance_system",
        charset="utf8mb4",
        cursorclass=DictCursor
        )

