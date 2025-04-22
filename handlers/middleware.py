from aiogram.types import Message
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram import Bot
from contextlib import suppress
import aiosqlite

DB_NAME = "mybot.db"

class GroupUserMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        super().__init__()
        self.bot = bot

    async def __call__(self, handler, event: Message, data: dict):
        chat = event.chat

        async with aiosqlite.connect(DB_NAME) as db:
            if chat.type in ["group", "supergroup"]:
                # Guruh ishtirokchilar sonini olishga harakat qilamiz
                with suppress(Exception):
                    member_count = await self.bot.get_chat_member_count(chat.id)
                # DBga qo‘shamiz yoki mavjud bo‘lsa, yangilaymiz
                await db.execute("""
                    INSERT INTO groups (group_id, number)
                    VALUES (?, ?)
                    ON CONFLICT(group_id) DO UPDATE SET
                        number = excluded.number,
                        bot_status = 1
                """, (chat.id, member_count))
            elif chat.type == "private":
                await db.execute("""
                    INSERT OR IGNORE INTO users (user_id)
                    VALUES (?)
                """, (chat.id,))
            await db.commit()

        return await handler(event, data)
