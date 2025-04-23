from aiogram.types import Message
from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram import Bot
from contextlib import suppress
import asyncpg

class GroupUserMiddleware(BaseMiddleware):
    def __init__(self, bot: Bot, pool):
        super().__init__()
        self.bot = bot
        self.pool = pool

    async def __call__(self, handler, event: Message, data: dict):
        chat = event.chat

        async with self.pool.acquire() as conn:
            if chat.type in ["group", "supergroup"]:
                # Guruh a’zolar sonini olishga harakat qilamiz
                with suppress(Exception):
                    member_count = await self.bot.get_chat_member_count(chat.id)

                await conn.execute("""
                    INSERT INTO groups (group_id, number, bot_status)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (group_id) DO UPDATE SET
                        number = EXCLUDED.number,
                        bot_status = 1
                """, chat.id, member_count)
            elif chat.type == "private":
                await conn.execute("""
                    INSERT INTO users (user_id)
                    VALUES ($1)
                    ON CONFLICT (user_id) DO NOTHING
                """, chat.id)

        return await handler(event, data)

