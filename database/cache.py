# admin_cache.py

import asyncio
from datetime import datetime, timedelta

admin_cache = {}  # {chat_id: {"admins": set(), "updated_at": datetime}}

ADMIN_CACHE_TTL = timedelta(minutes=10)  # 10 daqiqa cache muddati

async def get_admins(chat_id: int, bot) -> set:
    now = datetime.now()

    if chat_id in admin_cache:
        cache_data = admin_cache[chat_id]
        if now - cache_data["updated_at"] < ADMIN_CACHE_TTL:
            return cache_data["admins"]  # cache'dan olamiz

    try:
        members = await bot.get_chat_administrators(chat_id)
        admin_ids = {m.user.id for m in members} | {1087968824}
        admin_cache[chat_id] = {
            "admins": admin_ids,
            "updated_at": now
        }
        return admin_ids
    except Exception as e:
        print(f"Adminlar ro‘yxatini olishda xatolik: {e}")
        return set()
