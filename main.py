import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database.frombase import init_db
from handlers.users import user_router
from handlers.groups import group_router


async def main():
    await init_db()
    # logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(group_router)
    dp.include_router(user_router)

    # await dp.start_polling(bot)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
