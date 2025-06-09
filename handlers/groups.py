import asyncio
import re
import logging
from datetime import timedelta
from typing import List, Optional, Tuple

from aiogram import Router, Bot, F
from aiogram.enums import ChatType, MessageEntityType
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import ChatMemberUpdated
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.types import Message, ChatPermissions, User, ChatMember

from config import cur
from database.cache import get_admins
from database.frombase import (
    add_member, add_channel, remove_channel, remove_members_by_user,
    remove_all_members, get_total_by_user, get_top_adders, get_required_channels,
    is_user_subscribed_all_channels, check_user_requirement, update_user_status
)
from handlers.functions import classify_admin, increment_user_comment, get_top_commenters, delete_group_comments

logger = logging.getLogger(__name__)
group_router = Router()


# === FILTERS ===
class IsGroupMessage(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}


class HasLink(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if not message.entities:
            return False

        return any(
            entity.type in {MessageEntityType.URL, MessageEntityType.TEXT_LINK}
            for entity in message.entities
        )


class IsJoinOrLeft(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.new_chat_members or message.left_chat_member)


# === KIRDI-CHIQDI TOZALASH ===
@group_router.message(IsGroupMessage(), IsJoinOrLeft())
async def handle_group_join_left(message: Message, bot: Bot) -> None:
    print("galdiii")
    """Handle new members joining or leaving the group"""
    if message.new_chat_members:
        for new_member in message.new_chat_members:
            if message.from_user.id != new_member.id:
                await add_member(message, new_member.id)

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")


@group_router.chat_member()
async def handle_chat_member_update(event: ChatMemberUpdated, bot: Bot):
    # Bot o'zgarishi
    if event.new_chat_member.user.id == bot.id:
        return

    # User boshqa userni qo‘shdi (member bo'lmagan → member bo'ldi)
    if event.old_chat_member.status in {"left", "kicked"} and event.new_chat_member.status == "member":
        if event.from_user.id != event.new_chat_member.user.id:
            # Boshqa user uni qo‘shgan bo‘lsa
            print(f"{event.from_user.full_name} ➕ {event.new_chat_member.user.full_name}")
            await add_member(event, event.new_chat_member.user.id)
            # Xabarni topib o‘chirishga harakat qilamiz (oxirgi 1-2 ta xabarni tekshirib)


# === HAVOLALARNI O'CHIRISH ===
@group_router.message(IsGroupMessage(), HasLink())
async def handle_links(message: Message) -> None:
    """Delete messages containing links from non-admins"""
    if await classify_admin(message):
        return

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")

    user_id = message.from_user.id
    name = message.from_user.full_name
    await message.answer(
        f'<a href="tg://user?id={user_id}">{name}</a> - siz reklama yubordingiz.',
        parse_mode="HTML"
    )


# === ADMIN COMMANDS ===
@group_router.message(Command("start"), IsGroupMessage())
async def handle_get_channel(message: Message) -> None:
    """Delete /start command in groups"""
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")


@group_router.message(Command("reset"), IsGroupMessage())
async def handle_reset(message: Message) -> None:
    """Reset user statuses in group"""
    if await classify_admin(message):
        await update_user_status(message)

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")


@group_router.message(Command("help"), IsGroupMessage())
async def handle_info(message: Message) -> None:
    """Show info about available commands"""
    if not await classify_admin(message):
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if not all_ok:
            try:
                await message.delete()
            except Exception as e:
                logger.warning(f"Xabarni o'chirishda xatolik: {e}")

            kanal_list = '\n'.join(missing)
            await message.answer(
                f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                parse_mode="HTML"
            )
            return
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
    await message.answer(text=help_text, parse_mode="HTML")


# === MAJBURIY A'ZO QO'SHISH SOZLAMALARI ===
@group_router.message(IsGroupMessage(), F.text == "/majburoff")
async def disable_required_add_count(message: Message) -> None:
    """Disable required member adding"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    group_id = message.chat.id
    cur.execute("""
        INSERT INTO group_requirement (group_id, required_count)
        VALUES (%s, 0)
        ON CONFLICT (group_id) DO UPDATE SET required_count = 0
    """, (group_id,))

    await message.reply("❌ A'zo qo'shish talabi bekor qilindi.")


@group_router.message(IsGroupMessage(), F.text.startswith("/majbur"))
async def set_required_add_count(message: Message) -> None:
    """Set required member count to add"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    match = re.match(r"/majbur\s+(\d+)", message.text)
    if not match:
        await message.reply("Iltimos, sonni kiriting: /majbur 3")
        return

    required_count = int(match.group(1))
    group_id = message.chat.id

    cur.execute("""
        INSERT INTO group_requirement (group_id, required_count)
        VALUES (%s, %s)
        ON CONFLICT (group_id) DO UPDATE SET required_count = EXCLUDED.required_count
    """, (group_id, required_count))

    await message.reply(f"✅ Endi har bir foydalanuvchi {required_count} ta a'zo qo'shishi shart.")


# === KANAL BOSHQARISH ===
@group_router.message(Command("kanallar"), IsGroupMessage())
async def handle_get_channel(message: Message, bot: Bot) -> None:
    """List all connected channels"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    channels = await get_required_channels(message.chat.id)
    if not channels:
        await message.answer("Hech qanday kanal topilmadi!")
        return

    usernames = []
    for channel_id in channels:
        try:
            chat = await bot.get_chat(channel_id)
            usernames.append(f"@{chat.username}" if chat.username else chat.title)
        except Exception as e:
            logger.warning(f"Kanal ma'lumotlarini olishda xatolik: {e}")
            usernames.append(str(channel_id))

    await message.answer("Ulangan kanallar:\n" + '\n'.join(usernames))


@group_router.message(Command("kanal"), IsGroupMessage())
async def handle_add_channel(message: Message, command: CommandObject, bot: Bot) -> None:
    """Add channel to required list"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    if not command.args:
        await message.reply("❗ Kanal username-ni kiriting: /kanal @username")
        return

    channel_username = command.args.strip()
    if not channel_username.startswith("@"):
        await message.reply("❗ To'g'ri formatda yuboring: @username")
        return

    try:
        channel = await bot.get_chat(channel_username)
        await add_channel(message.chat.id, channel.id)
        await message.reply(f"✅ {channel_username} bazaga qo'shildi.")
    except Exception as e:
        logger.warning(f"Kanalni olishda xatolik: {e}")
        await message.reply("❌ Kanal topilmadi yoki bot kanal admini emas.")


@group_router.message(Command("kanald"), IsGroupMessage())
async def handle_remove_channel(message: Message, command: CommandObject, bot: Bot) -> None:
    """Remove channel from required list"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    if not command.args:
        await message.reply("❗ Kanal username-ni kiriting: /kanald @username")
        return

    channel_username = command.args.strip()
    if not channel_username.startswith("@"):
        await message.reply("❗ To'g'ri formatda yuboring: @username")
        return

    try:
        channel = await bot.get_chat(channel_username)
        await remove_channel(message.chat.id, channel.id)
        await message.reply(f"🗑️ {channel_username} ushbu guruhdan o'chirildi.")
    except Exception as e:
        logger.warning(f"Kanalni olishda xatolik: {e}")
        await message.reply("❌ Kanal topilmadi yoki bot kanalga kira olmayapti.")


# === TOZALASH KOMANDALARI ===
@group_router.message(Command("cleanuser"), IsGroupMessage())
async def handle_clean_user(message: Message) -> None:
    """Clean members added by specific user"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    if not message.reply_to_message:
        await message.reply("❗ Bu komanda reply shaklida yuborilishi kerak.")
        return

    target_user = message.reply_to_message.from_user
    await remove_members_by_user(message.chat.id, target_user.id)
    await message.reply(
        f"🧹 {target_user.full_name} (ID: <code>{target_user.id}</code>) "
        "tomonidan qo'shilganlar o'chirildi.",
        parse_mode="HTML"
    )


@group_router.message(Command("cleangroup"), IsGroupMessage())
async def handle_clean_group(message: Message) -> None:
    """Clean all added members in group"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    await remove_all_members(message.chat.id)
    await message.reply("🧨 Guruhdagi barcha foydalanuvchilarning qo'shganlari o'chirildi.")


@group_router.message(Command("izohlard"), IsGroupMessage())
async def handle_clean_group(message: Message) -> None:
    """Clean all added members in group"""
    if not await classify_admin(message):
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Xabarni o'chirishda xatolik: {e}")
        return

    await delete_group_comments(message.chat.id)
    await message.reply("🧨 Guruhdagi barcha izoh ma'lumotlari tozalandi")


# === STATISTIKA KOMANDALARI ===
async def get_user_mention(bot: Bot, user_id: int) -> str:
    """Get user mention with fallback to ID"""
    try:
        user = await bot.get_chat(user_id)
        name = f"@{user.username}" if user.username else user.full_name
        return f'<a href="tg://user?id={user_id}">{name}</a>'
    except Exception as e:
        logger.warning(f"Foydalanuvchi ma'lumotlarini olishda xatolik: {e}")
        return str(user_id)


@group_router.message(Command("count"), IsGroupMessage())
async def handle_my_count(message: Message, bot: Bot) -> None:
    """Show how many members user has added"""
    if not await classify_admin(message):
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if not all_ok:
            try:
                await message.delete()
            except Exception as e:
                logger.warning(f"Xabarni o'chirishda xatolik: {e}")

            kanal_list = '\n'.join(missing)
            await message.answer(f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                                 f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                                 parse_mode="HTML")
            return

    total = await get_total_by_user(message.chat.id, message.from_user.id)
    await message.reply(f"📊 Siz ushbu guruhga {total} ta foydalanuvchini qo'shgansiz.")


@group_router.message(Command("replycount"), IsGroupMessage())
async def handle_reply_count(message: Message, bot: Bot) -> None:
    """Show how many members replied user has added"""
    if not await classify_admin(message):
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if not all_ok:
            try:
                await message.delete()
            except Exception as e:
                logger.warning(f"Xabarni o'chirishda xatolik: {e}")

            kanal_list = '\n'.join(missing)
            await message.answer(f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                                 f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                                 parse_mode="HTML")
            return

    if not message.reply_to_message:
        await message.reply("❗ Bu komanda faqat reply shaklida ishlaydi.")
        return

    replied_user = message.reply_to_message.from_user
    total = await get_total_by_user(message.chat.id, replied_user.id)

    mention = await get_user_mention(bot, replied_user.id)
    await message.reply(
        f"👤 {mention} (ID: <code>{replied_user.id}</code>) "
        f"ushbu guruhga {total} ta foydalanuvchini qo'shgan.",
        parse_mode="HTML"
    )


@group_router.message(Command("top"), IsGroupMessage())
async def handle_top(message: Message, bot: Bot) -> None:
    """Show top members who added most users"""
    if not await classify_admin(message):
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if not all_ok:
            try:
                await message.delete()
            except Exception as e:
                logger.warning(f"Xabarni o'chirishda xatolik: {e}")

            kanal_list = '\n'.join(missing)
            await message.answer(f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                                 f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                                 parse_mode="HTML")
            return

    top_users = await get_top_adders(message.chat.id, limit=20)

    if not top_users:
        await message.reply("📉 Hali hech kim foydalanuvchi qo'shmagan.")
        return

    text = "🏆 <b>Eng ko'p foydalanuvchi qo'shganlar:</b>\n\n"
    for i, (user_id, count) in enumerate(top_users, start=1):
        try:
            user = await bot.get_chat_member(message.chat.id, user_id)
            full_name = user.user.full_name
            mention = f'<a href="tg://user?id={user_id}">{full_name}</a>'
            text += f"{i}. {mention} — {count} ta\n"
        except Exception as e:
            logger.warning(f"Foydalanuvchini olishda xatolik: {e}")
            continue

    await message.reply(text, parse_mode="HTML")


@group_router.message(Command("izohlar"), IsGroupMessage())
async def handle_comments(message: Message, bot: Bot) -> None:
    """Show top members by comment count and average length"""
    if not await classify_admin(message):
        all_ok, missing = await is_user_subscribed_all_channels(message)
        if not all_ok:
            try:
                await message.delete()
            except Exception as e:
                logger.warning(f"Xabarni o'chirishda xatolik: {e}")

            kanal_list = '\n'.join(missing)
            await message.answer(
                f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a> '
                f'❗Iltimos, quyidagi kanallarga obuna bo‘ling:\n{kanal_list}',
                parse_mode="HTML"
            )
            return

    top_users = await get_top_commenters(message.chat.id, limit=20)

    if not top_users:
        await message.reply("💬 Hali hech kim izoh yozmagan.")
        return

    text = "💬 <b>Eng ko‘p izoh yozganlar:</b>\n\n"
    for i, (user_id, count, avg_len) in enumerate(top_users, start=1):
        try:
            member = await bot.get_chat_member(message.chat.id, user_id)
            full_name = member.user.full_name
            mention = f'<a href="tg://user?id={user_id}">{full_name}</a>'
            text += f"{i}. {mention} — {count} ta izoh, o‘rtacha {avg_len} ta belgi\n"
        except Exception as e:
            print(f"[x] Foydalanuvchini olishda xatolik: {e}")
            continue

    await message.reply(text, parse_mode="HTML")


# kayp

def is_reply_in_comment_thread(message: Message) -> bool:
    """
    Bu funksiya xabar comment thread ichida yozilgan (hatto reply bo‘lsa ham) holatlarni aniqlaydi.
    Oddiy guruhdagi reply'larni esa False qiladi.
    """

    # JSON ko‘rinishda xabarni print qilish
    print("🔎 KELGAN XABAR:")
    print(message.model_dump_json(indent=2))  # chiroyli formatda

    # 1. Oddiy guruhdagi reply (userdan userga) — False
    reply = message.reply_to_message
    if reply and reply.from_user and not message.message_thread_id:
        return False

    # 2. Agar bu thread (mavzu yoki kommentariya) ichida yozilgan bo‘lsa — True
    if message.message_thread_id is not None:
        return True

    # 3. Yoki bu avtomatik forward qilingan kanal postiga reply bo‘lsa — True
    if reply and reply.forward_from_chat and reply.is_automatic_forward:
        return True

    # 4. Aks holda — bu komment emas
    return False


# === FOYDALANUVCHI TEKSHIRISH ===
@group_router.message(IsGroupMessage())
async def check_user_access(message: Message, bot: Bot) -> None:
    """Check user subscriptions and added members"""
    user = message.from_user
    chat_id = message.chat.id
    user_id = user.id

    # Adminlar tekshirilmaydi
    if await classify_admin(message):
        if is_comment_thread(message):
            await increment_user_comment(group_id=chat_id, user_id=user_id, message_text=message.text or "", message_id=message.message_id)
        return

    # Kanalga obuna tekshiruvi
    all_ok, missing_channels = await is_user_subscribed_all_channels(message)

    # Odam qo'shish tekshiruvi
    is_ok, need_number = await check_user_requirement(message)

    # Agar hamma talablar bajarilgan bo'lsa, hech nima qilinmaydi
    if all_ok and is_ok:
        if is_comment_thread(message):
            await increment_user_comment(group_id=chat_id, user_id=user_id, message_text=message.text or "", message_id=message.message_id)
        return

    # Xabarni o'chirishga urinish
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")

    # Ogohlantirish matnini shakllantirish
    warn_text = f'<a href="tg://user?id={user_id}">{user.full_name}</a>❗\n'

    if not all_ok:
        kanal_list = '\n'.join(missing_channels)
        warn_text += f'Quyidagi kanallarga obuna bo‘ling:\n{kanal_list}\n'

    if not is_ok:
        warn_text += f'Siz yana {need_number}-ta odam qo‘shishingiz kerak\n'

    # Ogohlantirish xabari yuborish
    try:
        warn_msg = await message.answer(warn_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Ogohlantirish xabarini yuborishda xatolik: {e}")
        return

    # 10 soniyaga yozishni cheklash
    chat_member = await bot.get_chat_member(chat_id, user_id)
    can_send_messages = chat_member.can_send_messages
    can_send_media_messages = chat_member.can_send_media_messages
    can_send_polls = chat_member.can_send_polls
    can_send_other_messages = chat_member.can_send_other_messages
    can_add_web_page_previews = chat_member.can_add_web_page_previews
    can_change_info = chat_member.can_change_info
    can_invite_users = chat_member.can_invite_users
    can_pin_messages = chat_member.can_pin_messages
    try:
        until_timestamp = int((message.date + timedelta(seconds=10)).timestamp())
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages = False,
                can_send_media_messages = False,
                can_send_polls = False,
                can_send_other_messages = False,
                can_add_web_page_previews = False,
                can_change_info = False,
                can_invite_users = True,
                can_pin_messages = False
            ),
            until_date=until_timestamp
        )

    except Exception as e:
        logger.warning(f"Foydalanuvchini cheklashda xatolik: {e}")

    # 10 soniyadan so'ng cheklovni olib tashlash
    await asyncio.sleep(10)

    # Ogohlantirish xabarini o'chirish
    try:
        await bot.delete_message(chat_id, warn_msg.message_id)
    except Exception as e:
        logger.warning(f"Ogohlantirish xabarini o'chirishda xatolik: {e}")

    # Foydalanuvchining yozish huquqini tiklash
    try:
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(
                can_send_messages=can_send_messages,
                can_send_media_messages=can_send_media_messages,
                can_send_polls=can_send_polls,
                can_send_other_messages=can_send_other_messages,
                can_add_web_page_previews=can_add_web_page_previews,
                can_change_info=can_change_info,
                can_invite_users=can_invite_users,
                can_pin_messages=can_pin_messages
            )
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchi huquqlarini tiklashda xatolik: {e}")
