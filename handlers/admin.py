import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command

from config import ADMIN_ID

admin_router = Router()


@admin_router.message(F.text == "/admin")
async def admin_handler(msg: Message):
    if msg.from_user.id not in ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="♻️ Yangilash", callback_data="admin_refresh")]
    ])
    await msg.answer("Admin panelga xush kelibsiz!", reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery):
    await callback.answer()
    async with aiosqlite.connect("mybot.db") as db:
        # Nechta user bor
        users_count = await db.execute_fetchone("SELECT COUNT(*) FROM users")
        users_count = users_count[0] if users_count else 0

        # Guruhlar va a'zolar soni
        groups = await db.execute_fetchall("SELECT bot_status, number FROM groups")
        group_count = len(groups)
        total_members = sum(row[1] for row in groups)
        admin_count = sum(1 for row in groups if row[0])  # bot_status=True bo'lganlar soni

    text = (
        f"📊 <b>Statistika:</b>\n\n"
        f"👤 Foydalanuvchilar (private): <b>{users_count}</b>\n"
        f"👥 Guruhlar soni: <b>{group_count}</b>\n"
        f"🤖 Bot admin bo‘lgan guruhlar: <b>{admin_count}</b>\n"
        f"👨‍👩‍👧‍👦 Jami a'zolar soni: <b>{total_members}</b>"
    )
    await callback.message.edit_text(text, reply_markup=callback.message.reply_markup)
    


@admin_router.callback_query(F.data == "admin_refresh")
async def admin_refresh_handler(callback: CallbackQuery, bot):
    await callback.answer()
    updated = 0
    async with aiosqlite.connect("mybot.db") as db:
        groups = await db.execute_fetchall("SELECT group_id FROM groups")
        for (group_id,) in groups:
            try:
                # A'zolar sonini olish
                count = await bot.get_chat_member_count(group_id)
                # Adminligini tekshirish
                me = await bot.get_chat_member(group_id, bot.id)
                is_admin = me.status in ("administrator", "creator")

                # Yangilash
                await db.execute("""
                    UPDATE groups
                    SET number = ?, bot_status = ?
                    WHERE group_id = ?
                """, (count, int(is_admin), group_id))
                updated += 1
            except Exception as e:
                print(f"Guruh {group_id} yangilashda xatolik: {e}")
        await db.commit()

    await callback.message.edit_text(f"✅ Yangilandi! {updated} ta guruh tekshirildi.", reply_markup=callback.message.reply_markup) 
