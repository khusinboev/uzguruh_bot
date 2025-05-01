import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, dp, bot
from database.frombase import init_db
from handlers.admin import admin_router
from handlers.middleware import GroupUserMiddleware
from handlers.users import user_router
from handlers.groups import group_router


async def main():
    await init_db()
    # logging.basicConfig(level=logging.INFO)
    dp.update.middleware(GroupUserMiddleware(bot))

    dp.include_router(group_router)
    dp.include_router(user_router)
    dp.include_router(admin_router)

    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
