import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
USERNAME = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASS")
DATABASE = os.getenv("DATABASE")

conn = psycopg2.connect(database=DATABASE, user=USERNAME, password=PASSWORD, host="localhost", port=5432)
cur = conn.cursor()

ADMIN_ID = [1918760732, 619839487, 5246872049]
