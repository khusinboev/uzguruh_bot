from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import CommandStart

user_router = Router()

@user_router.message(CommandStart())
async def start_handler(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Guruhga qo‘shish",
                url="https://t.me/uzguruh_bot?startgroup=start"
            )
        ]
    ])

    text = (
        "<b>Assalomu alaykum!</b>\n\n"
        "Ushbu bot guruhingizda reklamalarni avtomatik aniqlab, tozalashga yordam beradi.\n"
        "Iltimos, <b>botni guruhingizga qo‘shing</b> va unga admin huquqlarini bering.\n\n"
        "Botni guruhga qo‘shish uchun quyidagi tugmani bosing:"
    )

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")