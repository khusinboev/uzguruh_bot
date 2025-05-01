from aiogram import Router, F, Bot
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ReplyKeyboardMarkup, \
    KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from typing import List, Optional

from config import ADMIN_ID, cur, conn, bot

admin_router = Router()

class MsgState(StatesGroup):
    forward_msg = State()
    send_msg = State()

@admin_router.message(Command("admin"))
async def admin_handler(msg: Message) -> None:
    """Admin panelni ko'rsatish"""
    if msg.from_user.id not in ADMIN_ID:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="♻️ Yangilash", callback_data="admin_refresh")],
        [InlineKeyboardButton(text="📨Forward xabar yuborish", callback_data="send_forward")],
        [InlineKeyboardButton(text="📬Oddiy xabar yuborish", callback_data="send_simple")]
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


markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]])
@admin_router.callback_query(F.data == "send_forward")
async def admin_stats_handler(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.delete()
    await call.answer()
    await call.message.answer("Forward yuboriladigan xabarni yuboring", reply_markup=markup)
    await state.set_state(MsgState.forward_msg)


@admin_router.message(MsgState.forward_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_forward_to_all(message: Message, state: FSMContext):
    await state.clear()
    cur.execute("SELECT group_id FROM public.groups")
    rows = cur.fetchall()
    rows = [row[0] for row in rows]
    cur.execute("SELECT user_id FROM public.users")
    rows2 = cur.fetchall()
    rows2 = [row2[0] for row2 in rows2]
    num = 0
    for row in rows+rows2:
        num += await forward_send_msg(bot=bot, from_chat_id=message.chat.id, message_id=message.message_id, chat_id=row)

    await message.bot.send_message(chat_id=message.chat.id,
                                   text=f"Xabar yuborish yakunlandi, xabaringiz {num} ta odamga yuborildi",
                                   reply_markup=ReplyKeyboardRemove())


@admin_router.callback_query(F.data == "send_simple")
async def admin_stats_handler(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.delete()
    await call.answer()
    await call.message.answer("Yuborilishi kerak bo'lgan xabarni yuboring",
                         reply_markup=markup)
    await state.set_state(MsgState.send_msg)


@admin_router.message(MsgState.send_msg, F.chat.type == ChatType.PRIVATE, F.from_user.id.in_(ADMIN_ID))
async def send_text_to_all(message: Message, state: FSMContext):
    await state.clear()
    cur.execute("SELECT group_id FROM public.groups")
    rows = cur.fetchall()
    rows = [row[0] for row in rows]
    cur.execute("SELECT user_id FROM public.users")
    rows2 = cur.fetchall()
    rows2 = [row2[0] for row2 in rows2]
    num = 0
    for row in rows + rows2:
        num += await send_message_chats(bot=bot, from_chat_id=message.chat.id, message_id=message.message_id, chat_id=row)

    await message.answer(f"Xabar yuborish yakunlandi, xabaringiz {num} ta odamga yuborildi", reply_markup=ReplyKeyboardRemove())


async def forward_send_msg(bot: Bot, chat_id: int, from_chat_id: int, message_id: int) -> int:
    try:
        await bot.forward_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
        return 1
    except (TelegramAPIError, TelegramBadRequest):
        pass
    except Exception as e:
        print(f"Xatolik (forward): {e}")
    return 0



async def send_message_chats(bot: Bot, chat_id: int, from_chat_id: int, message_id: int) -> int:
    try:
        await bot.copy_message(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id)
        return 1
    except (TelegramAPIError, TelegramBadRequest):
        pass
    except Exception as e:
        print(f"Xatolik (copy): {e}")
    return 0
