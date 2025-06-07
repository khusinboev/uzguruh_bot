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
        "<b>🤖 Bot Buyruqlari</b>\n\n"
        "<b>🫂 Foydalanuvchilar uchun:</b>\n"
        "🔹 <b>/top</b> – Eng ko‘p foydalanuvchi qo‘shganlar reytingi\n"
        "🔹 <b>/replycount</b> – Sizga berilgan javoblar statistikasi\n"
        "🔹 <b>/count</b> – Shaxsiy statistikangiz\n\n"
        "<b>👨‍💻 Administratorlar uchun:</b>\n"
        "🔹 <b>/kanallar</b> – Ulangan kanallar ro‘yxati\n"
        "🔹 <b>/kanal @username</b> – Yangi kanalni ulash\n"
        "🔹 <b>/kanald @username</b> – Kanalni ro‘yxatdan olib tashlash\n"
        "🔹 <b>/cleanuser</b> – Foydalanuvchining qo‘shganlarini tozalash\n"
        "🔹 <b>/cleangroup</b> – Guruhdagi barcha qo‘shilgan foydalanuvchilarni tozalash\n"
        "🔹 <b>/izohlar</b> – Guruhdagi top 20ta izohchilar ro'yxati\n"
        "🔹 <b>/izohlard</b> – Guruhdagi izoh ma'lumotlarini tozalash\n"
    )
    await message.answer(help_text, parse_mode="HTML")