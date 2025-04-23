from aiogram import Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command 

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


@user_router.message(Command("help"))
async def help_handler(message: Message):
    help_text = (
        "<b>🆘 Yordam</b>\n\n"
        "🔹 <b>/top</b> - Top-20 odam qo'shganlar\n" 
        "🔹 <b>/replycount</b> - Qancha odam qo'shganini hisoblash\n"
        "🔹 <b>/count</b> - Siz qancha odam qo'shganingizni hisoblash \n\n"
        "<i>👨‍💻Adminlar uchun:</i>\n"
        "🔹 <b>/kanallar</b> - Kanallar ro'yxatini olish\n"
        "🔹 <b>/kanal @username</b> - Kanal qo'shish\n"
        "🔹 <b>/kanald @username</b> - Kanalni o'chirish\n"
        "🔹 <b>/cleanuser</b> - Reply qilingan odamni ma'lumotlarini o'chirish, qancha odam qo'shgani haqidagi ma'lumot\n"
        "🔹 <b>/cleangroup</b> - Butun guruhni qancha odam qo'shgani haqidagi ma'lumotlarni o'chirish"
    )
    await message.answer(help_text, parse_mode="HTML")