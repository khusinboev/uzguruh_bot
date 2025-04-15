import asyncio
import logging
from datetime import timedelta

from aiogram import Router, Bot
from aiogram.enums import ChatType, MessageEntityType
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import Message, ChatPermissions

from database.cache import get_admins
from database.frombase import add_member, add_channel, remove_channel, \
    remove_members_by_user, remove_all_members, get_total_by_user, get_top_adders, \
    get_required_channels, is_user_subscribed  # bazaga yozuvchi funksiya

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

        for entity in message.entities:
            if entity.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK]:
                return True
        return False


class IsJoinOrLeft(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return bool(message.new_chat_members or message.left_chat_member)


# === KIRDI CHIQDI TOZALASH ===
@group_router.message(IsGroupMessage(), IsJoinOrLeft())
async def handle_group_join_left(message: Message, bot: Bot):
    if message.new_chat_members:
        for new_member in message.new_chat_members:
            # Agar user o‘zini o‘zi qo‘shmagan bo‘lsa, ya'ni birov qo‘shgan bo‘lsa
            if message.from_user.id != new_member.id:
                await add_member(
                    group_id=message.chat.id,
                    user_id=message.from_user.id,
                    member=new_member.id
                )

    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")


# === HAVOLALARNI O'CHRISH  ===
@group_router.message(IsGroupMessage(), HasLink())
async def handle_links(message: Message):
    # Agar bu forward qilingan post bo‘lsa (linked channel yoki boshqalar) — skip
    if message.forward_from_chat:
        return

    # Agar foydalanuvchi admin bo‘lsa — skip
    try:
        admin_ids = await get_admins(message.chat.id, message.bot)
        if message.from_user.id in admin_ids:
            return
    except Exception as e:
        logger.warning(f"Admin holatini tekshirishda xatolik: {e}")
        return  # xavfsizlik uchun chiqaramiz

    # O'chirish va ogohlantirish
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirishda xatolik: {e}")

    user_id = message.from_user.id
    await message.answer(
        f'<a href="tg://user?id={user_id}">{user_id}</a> - siz reklama yubordingiz.',
        parse_mode="HTML"
    )


# === info ===
@group_router.message(Command("info"), IsGroupMessage())
async def handle_get_channel(message: Message, bot: Bot):
    # Kanal ro‘yxatini olish
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        unsubscribed_channels = []
        for channel_id in await get_required_channels(message.chat.id):
            is_subscribed = await is_user_subscribed(bot, channel_id, message.from_user.id, message.chat.id)
            if not is_subscribed:
                unsubscribed_channels.append(channel_id)
        if unsubscribed_channels:
            # ❌ Xabarni o‘chirish (agar iloji bo‘lsa)
            try:
                await message.delete()
            except Exception:
                pass
            return  # Hammasi yaxshi, hech nima qilmaymiz
    await message.answer("""🫂Hamma uchun
/top
/replycount
/count

👨‍💻Adminlar uchun
/kanallar
/kanal
/kanald
/cleanuser
/cleangroup""")


# === kanal qo'shish ===
@group_router.message(Command("kanallar"), IsGroupMessage())
async def handle_get_channel(message: Message, command: CommandObject, bot: Bot):
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        try:
            await message.delete()
        except Exception:
            pass
        return  # Admin emas
    channels = await get_required_channels(message.chat.id)
    await message.answer("Ulangan kanallar:\n"+'\n@'.join((await message.bot.get_chat(i)).username for i in channels))


@group_router.message(Command("kanal"), IsGroupMessage())
async def handle_add_channel(message: Message, command: CommandObject, bot: Bot):
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        try:
            await message.delete()
        except Exception:
            pass
        return  # Admin emas

    if not command.args:
        await message.reply("❗ Kanal username-ni kiriting: /kanal @username")
        return

    channel_username = command.args.strip()
    if not channel_username.startswith("@"):
        await message.reply("❗ To‘g‘ri formatda yuboring: @username")
        return

    try:
        channel = await message.bot.get_chat(channel_username)
        await add_channel(message.chat.id, channel.id)
        await message.reply(f"✅ {channel_username} bazaga qo‘shildi.")
    except Exception as e:
        logger.warning(f"Kanalni olishda xatolik: {e}")
        await message.reply("❌ Kanal topilmadi yoki bot kanal admini emas.")

# === kanal ayirish ===
@group_router.message(Command("kanald"), IsGroupMessage())
async def handle_remove_channel(message: Message, command: CommandObject, bot: Bot):
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        try:
            await message.delete()
        except Exception:
            pass
        return  # Admin emas

    if not command.args:
        await message.reply("❗ Kanal username-ni kiriting: /kanald @username")
        return

    channel_username = command.args.strip()
    if not channel_username.startswith("@"):
        await message.reply("❗ To‘g‘ri formatda yuboring: @username")
        return

    try:
        channel = await message.bot.get_chat(channel_username)
        await remove_channel(message.chat.id, channel.id)
        await message.reply(f"🗑️ {channel_username} ushbu guruhdan o‘chirildi.")
    except Exception as e:
        logger.warning(f"Kanalni olishda xatolik: {e}")
        await message.reply("❌ Kanal topilmadi yoki bot kanalga kira olmayapti.")

# === clean by user ===
@group_router.message(Command("cleanuser"), IsGroupMessage())
async def handle_clean_user(message: Message, bot: Bot):
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        try:
            await message.delete()
        except Exception:
            pass
        return  # Admin emas

    if not message.reply_to_message:
        await message.reply("❗ Bu komanda reply shaklida yuborilishi kerak.")
        return

    target_user = message.reply_to_message.from_user
    await remove_members_by_user(message.chat.id, target_user.id)
    await message.reply(f"🧹 {target_user.full_name} (ID: <code>{target_user.id}</code>) tomonidan qo‘shilganlar o‘chirildi.", parse_mode="HTML")

# === clean all ===
@group_router.message(Command("cleangroup"), IsGroupMessage())
async def handle_clean_group(message: Message):
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        try:
            await message.delete()
        except Exception:
            pass
        return  # Admin emas

    await remove_all_members(message.chat.id)
    await message.reply("🧨 Guruhdagi barcha foydalanuvchilarning qo‘shganlari o‘chirildi.")

# === count by user ===
@group_router.message(Command("count"), IsGroupMessage())
async def handle_my_count(message: Message, bot: Bot):
    # Kanal ro‘yxatini olish
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        unsubscribed_channels = []
        for channel_id in await get_required_channels(message.chat.id):
            is_subscribed = await is_user_subscribed(bot, channel_id, message.from_user.id, message.chat.id)
            if not is_subscribed:
                unsubscribed_channels.append(channel_id)
        if unsubscribed_channels:
            # ❌ Xabarni o‘chirish (agar iloji bo‘lsa)
            try:
                await message.delete()
            except Exception:
                pass
            return  # Hammasi yaxshi, hech nima qilmaymiz
    total = await get_total_by_user(message.chat.id, message.from_user.id)
    await message.reply(
        f"📊 Siz ushbu guruhga {total} ta foydalanuvchini qo‘shgansiz."
    )

# === count by other user ===
@group_router.message(Command("replycount"), IsGroupMessage())
async def handle_reply_count(message: Message, bot: Bot):
    # Kanal ro‘yxatini olish
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        unsubscribed_channels = []
        for channel_id in await get_required_channels(message.chat.id):
            is_subscribed = await is_user_subscribed(bot, channel_id, message.from_user.id, message.chat.id)
            if not is_subscribed:
                unsubscribed_channels.append(channel_id)
        if unsubscribed_channels:
            # ❌ Xabarni o‘chirish (agar iloji bo‘lsa)
            try:
                await message.delete()
            except Exception:
                pass
            return  # Hammasi yaxshi, hech nima qilmaymiz

    if not message.reply_to_message:
        await message.reply("❗ Bu komanda faqat reply shaklida ishlaydi.")
        return

    replied_user = message.reply_to_message.from_user
    total = await get_total_by_user(message.chat.id, replied_user.id)

    await message.reply(
        f"👤 {replied_user.full_name} (ID: <code>{replied_user.id}</code>) ushbu guruhga {total} ta foydalanuvchini qo‘shgan.",
        parse_mode="HTML"
    )

# === top ===
@group_router.message(Command("top"), IsGroupMessage())
async def handle_top(message: Message, bot: Bot):
    # Kanal ro‘yxatini olish
    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id not in admin_ids:
        unsubscribed_channels = []
        for channel_id in await get_required_channels(message.chat.id):
            is_subscribed = await is_user_subscribed(bot, channel_id, message.from_user.id, message.chat.id)
            if not is_subscribed:
                unsubscribed_channels.append(channel_id)
        if unsubscribed_channels:
            # ❌ Xabarni o‘chirish (agar iloji bo‘lsa)
            try:
                await message.delete()
            except Exception:
                pass
            return  # Hammasi yaxshi, hech nima qilmaymiz

    top_users = await get_top_adders(message.chat.id, limit=20)

    if not top_users:
        await message.reply("📉 Hali hech kim foydalanuvchi qo‘shmagan.")
        return

    text = "🏆 <b>Eng ko‘p foydalanuvchi qo‘shganlar:</b>\n\n"
    for i, (user_id, count) in enumerate(top_users, start=1):
        mention = f'<a href="tg://user?id={user_id}">{user_id}</a>'
        text += f"{i}. {mention} — {count} ta\n"

    await message.reply(text, parse_mode="HTML")


# === check channel subscription ===
@group_router.message(IsGroupMessage())
async def check_channel_subscription(message: Message, bot: Bot):
    user = message.from_user
    chat_id = message.chat.id
    user_id = user.id

    admin_ids = await get_admins(message.chat.id, message.bot)
    if message.from_user.id in admin_ids:
        return

    # Kanal ro‘yxatini olish
    channel_ids = await get_required_channels(chat_id)
    if not channel_ids:
        return  # Agar kanal biriktirilmagan bo‘lsa, tekshirmaymiz

    unsubscribed_channels = []
    for channel_id in channel_ids:
        is_subscribed = await is_user_subscribed(bot, channel_id, user_id, chat_id)
        if not is_subscribed:
            unsubscribed_channels.append(channel_id)

    if not unsubscribed_channels:
        return  # Hammasi yaxshi, hech nima qilmaymiz

    # ❌ Xabarni o‘chirish (agar iloji bo‘lsa)
    try:
        await message.delete()
    except Exception:
        pass

    # 🔗 Kanal linklarini tayyorlash
    links = []
    for cid in unsubscribed_channels:
        try:
            chat = await bot.get_chat(cid)
            if chat.username:
                links.append(f"👉 @{chat.username}")
        except Exception:
            continue

    links_text = "\n".join(links) if links else "⚠️ Kanal havolalarini olishda xatolik yuz berdi."

    # ⚠️ Ogohlantiruvchi matn
    warn_text = (
        f'<a href="tg://user?id={user_id}">{user_id}</a> ❗Guruhda yozishdan oldin quyidagi kanallarga obuna bo‘ling:\n\n'
        f"{links_text}"
    )

    warn_msg = None
    try:
        warn_msg = await message.answer(warn_text, parse_mode="HTML")
    except Exception:
        pass

    # 🔒 10 soniyaga yozishni cheklash
    try:
        until_timestamp = int((message.date + timedelta(seconds=10)).timestamp())
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_timestamp
        )
    except Exception:
        pass

    # ⏱️ 10 soniyadan so‘ng ogohlantirish xabarini o‘chirish va yozish ruxsatini tiklash
    await asyncio.sleep(10)

    # Ogohlantirish xabarini o‘chirish
    if warn_msg:
        try:
            await bot.delete_message(chat_id, warn_msg.message_id)
        except Exception:
            pass

    # Foydalanuvchining yozish ruxsatini tiklash (agar hali ochilmagan bo‘lsa)
    try:
        await bot.restrict_chat_member(
            chat_id,
            user_id,
            permissions=ChatPermissions(can_send_messages=True)  # Yozishga ruxsat beriladi
        )
    except Exception:
        pass