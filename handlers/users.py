from aiogram import Router, types
from aiogram.filters import CommandStart

user_router = Router()

@user_router.message()
async def handle_start(message: types.Message):
    print("yo'qsinliqa galdi")
