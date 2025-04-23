from aiogram import Router, F, Bot
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
async def admin_stats_handler(callback: CallbackQuery, pool):
    await callback.answer("biroz kuting")
    async with pool.acquire() as conn:
        # Nechta user bor
        row = await conn.fetchrow("SELECT COUNT(*) FROM users")
        users_count = row["count"] if row else 0

        # Guruhlar va a'zolar soni
        groups = await conn.fetch("SELECT bot_status, number FROM groups")
        group_count = len(groups)
        total_members = sum(row["number"] for row in groups)
        admin_count = sum(1 for row in groups if row["bot_status"])

    text = (
        f"📊 <b>Statistika:</b>\n\n"
        f"👤 Foydalanuvchilar (private): <b>{users_count}</b>\n"
        f"👥 Guruhlar soni: <b>{group_count}</b>\n"
        f"🤖 Bot admin bo‘lgan guruhlar: <b>{admin_count}</b>\n"
        f"👨‍👩‍👧‍👦 Jami a'zolar soni: <b>{total_members}</b>"
    )
    await callback.message.edit_text(text, reply_markup=callback.message.reply_markup, parse_mode="html")


@admin_router.callback_query(F.data == "admin_refresh")
async def admin_refresh_handler(callback: CallbackQuery, bot: Bot, pool):
    await callback.answer("biroz kuting")
    updated = 0

    async with pool.acquire() as conn:
        groups = await conn.fetch("SELECT group_id FROM groups")
        for row in groups:
            group_id = row["group_id"]
            try:
                # A'zolar soni va adminligini tekshirish
                count = await bot.get_chat_member_count(group_id)
                me = await bot.get_chat_member(group_id, bot.id)
                is_admin = me.status in ("administrator", "creator")

                await conn.execute("""
                    UPDATE groups
                    SET number = $1, bot_status = $2
                    WHERE group_id = $3
                """, count, int(is_admin), group_id)
                updated += 1
            except Exception as e:
                print(f"Guruh {group_id} yangilashda xatolik: {e}")

    await callback.message.edit_text(f"✅ Yangilandi! {updated} ta guruh tekshirildi.", reply_markup=callback.message.reply_markup)
