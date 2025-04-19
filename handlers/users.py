from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

user_router = Router()

@user_router.message(CommandStart())
async def start_handler(message: Message):
    text = (
        "🇺🇿 <i>Guruhga qo'shish uchun pastdagi\n"
        "«➕ GURUHGA QO'SHISH ☑️» tugmasini bosing va guruhingizda administratorlik huquqini bering. Ko'proq ma'lumot...</i>\n"
        "🇷🇺 <i>Чтобы добавить в группу, нажмите кнопку\n"
        "«➕ GURUHGA QO'SHISH ☑️» и дайте права администратора. Больше информации...</i>\n"
        "🇬🇧 <i>To add to the group, press the button\n"
        "«➕ GURUHGA QO'SHISH ☑️» and give administrator rights. More information ...</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ GURUHGA QO‘SHISH ☑️",
                url="https://t.me/uzguruh_bot?startgroup=start"
            )
        ]
    ])

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")