from aiogram import Router, F, Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from typing import List, Optional

from config import ADMIN_ID, cur, conn

admin_router = Router()


@admin_router.message(Command("admin"))
async def admin_handler(msg: Message) -> None:
    """Admin panelni ko'rsatish"""
    if msg.from_user.id not in ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="♻️ Yangilash", callback_data="admin_refresh")]
    ])
    await msg.answer("Admin panelga xush kelibsiz!", reply_markup=keyboard)


@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: CallbackQuery) -> None:
    """Bot statistikasini ko'rsatish"""
    await callback.answer("Ma'lumotlar yuklanmoqda...")

    try:
        # Foydalanuvchilar soni
        cur.execute("SELECT COUNT(*) FROM users")
        users_count = cur.fetchone()[0] if cur.rowcount else 0

        # Guruhlar statistikasi
        cur.execute("SELECT bot_status, number FROM groups")
        groups = cur.fetchall()

        group_count = len(groups)
        total_members = sum(row[1] for row in groups) if groups else 0
        admin_count = sum(1 for row in groups if row[0]) if groups else 0

        text = (
            f"📊 <b>Statistika:</b>\n\n"
            f"👤 Foydalanuvchilar (private): <b>{users_count}</b>\n"
            f"👥 Guruhlar soni: <b>{group_count}</b>\n"
            f"🤖 Bot admin bo'lgan guruhlar: <b>{admin_count}</b>\n"
            f"👨‍👩‍👧‍👦 Jami a'zolar soni: <b>{total_members}</b>"
        )

        await callback.message.edit_text(
            text,
            reply_markup=callback.message.reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Statistika olishda xatolik: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)


@admin_router.callback_query(F.data == "admin_refresh")
async def admin_refresh_handler(callback: CallbackQuery, bot: Bot) -> None:
    """Guruhlarni yangilash"""
    await callback.answer("Yangilanish jarayonida...")
    updated = 0

    try:
        cur.execute("SELECT group_id FROM groups")
        groups = cur.fetchall()

        for row in groups:
            group_id = row[0]
            try:
                # A'zolar soni va adminligini tekshirish
                count = await bot.get_chat_member_count(group_id)
                me = await bot.get_chat_member(group_id, bot.id)
                is_admin = me.status in ("administrator", "creator")

                cur.execute("""
                    UPDATE groups
                    SET number = %s, bot_status = %s
                    WHERE group_id = %s
                """, (count, is_admin, group_id))
                conn.commit()
                updated += 1
            except Exception as e:
                print(f"Guruh {group_id} yangilashda xatolik: {e}")
                continue

        await callback.message.edit_text(
            f"✅ {updated} ta guruh muvaffaqiyatli yangilandi!",
            reply_markup=callback.message.reply_markup
        )
    except Exception as e:
        print(f"Yangilash jarayonida xatolik: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)