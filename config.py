import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
DATABASE = os.getenv("DATABASE")

ADMIN_ID = [1918760732, 619839487, 5246872049]