import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from database.frombase import init_db, create_pool
from handlers.admin import admin_router
from handlers.middleware import GroupUserMiddleware
from handlers.users import user_router
from handlers.groups import group_router


async def main():
    pool = await create_pool()
    await init_db(pool)
    # logging.basicConfig(level=logging.INFO)
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp["pool"] = pool
    dp.update.middleware(GroupUserMiddleware(bot, pool))

    dp.include_router(group_router)
    dp.include_router(user_router)
    dp.include_router(admin_router)

    # await dp.start_polling(bot)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
