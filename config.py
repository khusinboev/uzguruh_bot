import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
USERNAME = os.getenv("DB_USER")
PASSWORD = os.getenv("DB_PASS")
DATABASE = os.getenv("DATABASE")

print(USERNAME, PASSWORD, DATABASE)

ADMIN_ID = [1918760732, 619839487, 5246872049]