import os
import asyncio
import threading
import sqlite3
from contextlib import closing

from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

TOKEN = os.getenv("TOKEN")

ADMINS = [1739947062, 5655991466]

INFO_CHANNEL = "https://t.me/+rFs7nnx639BmNzgy"
FLUD_LINK = "https://t.me/+zTukwrwrqlgxOGUy"

FAQ_TEXT = """
❓ FAQ

• Как попасть во флуд?
Заполнить анкету и дождаться решения администрации.

• Когда рассмотрят заявку?
Как только администраторы будут свободны.

• Можно ли подать заявку повторно?
Если вы не забанены — да.
"""

RULES_TEXT = """
📖 Правила

1. Соблюдайте правила общения.
2. Уважайте участников.
3. Не устраивайте конфликты.
4. Следуйте указаниям администрации.
"""

ABOUT_FLUD_TEXT = """
🎭 О флуде

Общий флуд для общения участников разных фандомов.
"""

FANDOMS_TEXT = """
🌍 Фандомы

Обсуждение любых фандомов приветствуется.
"""

app = Flask(__name__)

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())


@app.route("/")
def home():
    return "BOT ONLINE"


def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def init_db():
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            fandom TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS applications(
            user_id INTEGER PRIMARY KEY,
            admin_msg_1 INTEGER,
            admin_msg_2 INTEGER
        )
        """)

        conn.commit()


def get_user(user_id):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE user_id=?",
            (user_id,)
        )
        return cur.fetchone()


def get_status(user_id):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM users WHERE user_id=?",
            (user_id,)
        )
        row = cur.fetchone()
        return row[0] if row else None


def save_user(user_id, username):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, status)
        VALUES (?, ?, 'pending')
        """, (user_id, username))

        conn.commit()


def update_profile(user_id, role, fandom):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        cur.execute("""
        UPDATE users
        SET role=?, fandom=?, status='pending'
        WHERE user_id=?
        """, (role, fandom, user_id))

        conn.commit()


def update_status(user_id, status):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        cur.execute(
            "UPDATE users SET status=? WHERE user_id=?",
            (status, user_id)
        )

        conn.commit()


def save_application(user_id, msg1, msg2):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        cur.execute("""
        INSERT OR REPLACE INTO applications
        (user_id, admin_msg_1, admin_msg_2)
        VALUES (?, ?, ?)
        """, (user_id, msg1, msg2))

        conn.commit()


def get_application(user_id):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        cur.execute("""
        SELECT admin_msg_1, admin_msg_2
        FROM applications
        WHERE user_id=?
        """, (user_id,))

        return cur.fetchone()


def stats():
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        total = cur.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        accepted = cur.execute(
            "SELECT COUNT(*) FROM users WHERE status='accepted'"
        ).fetchone()[0]

        rejected = cur.execute(
            "SELECT COUNT(*) FROM users WHERE status='rejected'"
        ).fetchone()[0]

        banned = cur.execute(
            "SELECT COUNT(*) FROM users WHERE status='banned'"
        ).fetchone()[0]

        pending = cur.execute(
            "SELECT COUNT(*) FROM users WHERE status='pending'"
        ).fetchone()[0]

        return total, accepted, rejected, banned, pending


class Register(StatesGroup):
    question = State()
    role = State()
    fandom = State()


class BroadcastState(StatesGroup):
    text = State()


def pending_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 Правила", callback_data="rules")],
            [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
            [InlineKeyboardButton(text="🎭 О флуде", callback_data="about")],
            [InlineKeyboardButton(text="🌍 Фандомы", callback_data="fandoms")]
        ]
    )


def admin_panel():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users")],
            [InlineKeyboardButton(text="📨 Заявки", callback_data="adm_apps")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")],
            [InlineKeyboardButton(text="🚫 Бан-лист", callback_data="adm_banlist")],
            [InlineKeyboardButton(text="👥 Участников во флуде", callback_data="adm_members")]
        ]
    )


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Не указан"
    )

    save_user(message.from_user.id, username)

    if get_status(message.from_user.id) == "banned":
        await message.answer("🚫 Вы заблокированы.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Открыть инфо-канал",
                    url=INFO_CHANNEL
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Я ознакомился",
                    callback_data="read_info"
                )
            ]
        ]
    )

    await state.clear()

    await message.answer(
        "Перед подачей заявки ознакомьтесь с инфо-каналом.",
        reply_markup=kb
    )


@dp.callback_query(F.data == "read_info")
async def read_info(callback: CallbackQuery, state: FSMContext):
    if get_status(callback.from_user.id) == "banned":
        await callback.answer("Вы заблокированы", show_alert=True)
        return

    await state.set_state(Register.question)

    await callback.message.answer(
        "Максимальный срок реста?"
    )

    await callback.answer()


@dp.message(Register.question)
async def question_step(message: Message, state: FSMContext):
    if message.text.strip().lower() != "3 недели":
        await message.answer(
            "❌ Неверно. Попробуйте ещё раз."
        )
        return

    await state.set_state(Register.role)

    await message.answer("🎭 Укажите роль:")


@dp.message(Register.role)
async def role_step(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(Register.fandom)

    await message.answer("🌍 Укажите фандом:")


@dp.message(Register.fandom)
async def fandom_step(message: Message, state: FSMContext):
    data = await state.get_data()

    role = data["role"]
    fandom = message.text

    username = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Не указан"
    )

    update_profile(
        message.from_user.id,
        role,
        fandom
    )

    text = (
        "📨 Новая заявка\n\n"
        f"Username: {username}\n"
        f"Telegram ID: {message.from_user.id}\n"
        f"Роль: {role}\n"
        f"Фандом: {fandom}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=f"accept:{message.from_user.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{message.from_user.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚫 Забанить",
                    callback_data=f"ban:{message.from_user.id}"
                )
            ]
        ]
    )

    ids = []

    for admin in ADMINS:
        msg = await bot.send_message(
            admin,
            text,
            reply_markup=kb
        )
        ids.append(msg.message_id)

    save_application(
        message.from_user.id,
        ids[0],
        ids[1]
    )

    await message.answer(
        "✅ Заявка отправлена администрации.",
        reply_markup=pending_menu()
    )

    await state.clear()


async def update_admin_messages(user_id, text):
    app_row = get_application(user_id)

    if not app_row:
        return

    for admin, msg_id in zip(ADMINS, app_row):
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=admin,
                message_id=msg_id
            )
        except Exception:
            pass


@dp.callback_query(F.data.startswith("accept:"))
async def accept_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split(":")[1])

    if get_status(user_id) != "pending":
        await callback.answer("Уже обработано")
        return

    update_status(user_id, "accepted")

    try:
        await bot.send_message(
            user_id,
            f"✅ Заявка одобрена.\n\n{FLUD_LINK}"
        )
    except Exception:
        pass

    await update_admin_messages(
        user_id,
        "✅ Пользователь принят"
    )

    await callback.answer("Принято")


@dp.callback_query(F.data.startswith("reject:"))
async def reject_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split(":")[1])

    if get_status(user_id) != "pending":
        await callback.answer("Уже обработано")
        return

    update_status(user_id, "rejected")

    try:
        await bot.send_message(
            user_id,
            "❌ Ваша заявка отклонена."
        )
    except Exception:
        pass

    await update_admin_messages(
        user_id,
        "❌ Пользователь отклонён"
    )

    await callback.answer("Отклонено")


@dp.callback_query(F.data.startswith("ban:"))
async def ban_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split(":")[1])

    update_status(user_id, "banned")

    try:
        await bot.send_message(
            user_id,
            "🚫 Вы заблокированы."
        )
    except Exception:
        pass

    await update_admin_messages(
        user_id,
        "🚫 Пользователь забанен"
    )

    await callback.answer("Забанен")


@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if message.from_user.id not in ADMINS:
        return

    await message.answer(
        "⚙️ Админ-панель",
        reply_markup=admin_panel()
    )


@dp.callback_query(F.data == "adm_stats")
async def admin_stats(callback: CallbackQuery):
    total, accepted, rejected, banned, pending = stats()

    await callback.message.answer(
        f"📊 Статистика\n\n"
        f"Всего пользователей: {total}\n"
        f"Принято: {accepted}\n"
        f"Отклонено: {rejected}\n"
        f"Забанено: {banned}\n"
        f"Ожидают: {pending}"
    )

    await callback.answer()


@dp.callback_query(F.data == "adm_users")
async def admin_users(callback: CallbackQuery):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        rows = cur.execute("""
        SELECT username,user_id,status
        FROM users
        ORDER BY rowid DESC
        LIMIT 20
        """).fetchall()

    text = "👥 Последние пользователи\n\n"

    for row in rows:
        text += (
            f"{row[0]}\n"
            f"ID: {row[1]}\n"
            f"Статус: {row[2]}\n\n"
        )

    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data == "adm_apps")
async def admin_apps(callback: CallbackQuery):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        rows = cur.execute("""
        SELECT username,user_id,role,fandom
        FROM users
        WHERE status='pending'
        """).fetchall()

    if not rows:
        await callback.message.answer("Нет ожидающих заявок.")
        await callback.answer()
        return

    text = "📨 Ожидающие заявки\n\n"

    for row in rows:
        text += (
            f"{row[0]}\n"
            f"ID: {row[1]}\n"
            f"Роль: {row[2]}\n"
            f"Фандом: {row[3]}\n\n"
        )

    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data == "adm_banlist")
async def admin_banlist(callback: CallbackQuery):
    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        rows = cur.execute("""
        SELECT username,user_id
        FROM users
        WHERE status='banned'
        """).fetchall()

    if not rows:
        await callback.message.answer("Бан-лист пуст.")
        await callback.answer()
        return

    text = "🚫 Бан-лист\n\n"

    for row in rows:
        text += f"{row[0]} | {row[1]}\n"

    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data == "adm_broadcast")
async def broadcast_menu(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BroadcastState.text)

    await callback.message.answer(
        "Введите текст рассылки."
    )

    await callback.answer()


@dp.message(Command("broadcast"))
async def broadcast_command(message: Message):
    if message.from_user.id not in ADMINS:
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        return

    text = parts[1]

    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        users = cur.execute("""
        SELECT user_id
        FROM users
        WHERE status='accepted'
        """).fetchall()

    sent = 0

    for user in users:
        try:
            await bot.send_message(user[0], text)
            sent += 1
        except Exception:
            pass

    await message.answer(
        f"Отправлено: {sent}"
    )


@dp.message(BroadcastState.text)
async def broadcast_fsm(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return

    with closing(sqlite3.connect("flud.db")) as conn:
        cur = conn.cursor()

        users = cur.execute("""
        SELECT user_id
        FROM users
        WHERE status='accepted'
        """).fetchall()

    sent = 0

    for user in users:
        try:
            await bot.send_message(user[0], message.text)
            sent += 1
        except Exception:
            pass

    await message.answer(
        f"Рассылка завершена.\nОтправлено: {sent}"
    )

    await state.clear()


@dp.callback_query(F.data == "adm_members")
async def members_count(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    try:
        chat = await bot.get_chat(FLUD_LINK)
        count = await bot.get_chat_member_count(chat.id)

        await callback.message.answer(
            f"👥 Участников: {count}"
        )
    except Exception:
        await callback.message.answer(
            "Не удалось получить количество участников.\n"
            "Добавьте бота администратором группы."
        )

    await callback.answer()


@dp.callback_query(F.data == "rules")
async def rules(callback: CallbackQuery):
    await callback.message.answer(RULES_TEXT)
    await callback.answer()


@dp.callback_query(F.data == "faq")
async def faq(callback: CallbackQuery):
    await callback.message.answer(FAQ_TEXT)
    await callback.answer()


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.message.answer(ABOUT_FLUD_TEXT)
    await callback.answer()


@dp.callback_query(F.data == "fandoms")
async def fandoms(callback: CallbackQuery):
    await callback.message.answer(FANDOMS_TEXT)
    await callback.answer()


async def main():
    init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    asyncio.run(main())