from aiogram.types import Message, Update
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram import Bot
from contextlib import suppress
from config import cur, conn


class GroupUserMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot):
        super().__init__()
        self.bot = bot
        self.cur = cur  # Psikopg2 yoki sinxron kutubxona bilan ishlash
        self.conn = conn  # Sinxron kutubxona bilan ishlash

    async def __call__(self, handler, event: Update, data: dict):
        message: Message = event.message  # Faqat message turlari uchun
        if message is None:
            return await handler(event, data)  # Message yo‘q bo‘lsa, middleware hech nima qilmasin
        chat = message.chat

        if chat.type in ["group", "supergroup"]:
            # Guruh a’zolar sonini olishga harakat qilamiz
            with suppress(Exception):
                member_count = await self.bot.get_chat_member_count(chat.id)

            # Botning guruhdagi adminligini tekshiramiz
            bot_member = await self.bot.get_chat_member(chat.id, self.bot.id)
            bot_status = True if bot_member.status in ['administrator', 'creator'] else False

            # Sinxron kutubxona bilan ishlash
            self.cur.execute("""
                INSERT INTO groups (group_id, number, bot_status)
                VALUES (%s, %s, %s)
                ON CONFLICT (group_id) DO UPDATE SET
                    number = EXCLUDED.number,
                    bot_status = EXCLUDED.bot_status
            """, (chat.id, member_count, bot_status))
        elif chat.type == "private":
            self.cur.execute("""
                INSERT INTO users (user_id)
                VALUES (%s)
                ON CONFLICT (user_id) DO NOTHING
            """, (chat.id,))
        self.conn.commit()  # Sinxron commit

        return await handler(event, data)