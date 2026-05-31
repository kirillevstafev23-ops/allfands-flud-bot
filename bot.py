import os
import asyncio
import threading
import sqlite3

from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("TOKEN")

ADMINS = [1739947062, 5655991466]

INFO_CHANNEL = "https://t.me/+rFs7nnx639BmNzgy"
FLUD_LINK = "https://t.me/+zTukwrwrqlgxOGUy"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

app = Flask(__name__)


@app.route("/")
def home():
    return "ALLFANDS FLUD BOT ONLINE"


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


def init_db():
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        role TEXT,
        fandom TEXT,
        status TEXT DEFAULT 'pending',
        banned INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()


init_db()


class Registration(StatesGroup):
    role = State()
    fandom = State()
    question = State()


class Mailing(StatesGroup):
    text = State()


def add_user(user_id, username, full_name):
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR IGNORE INTO users
    (user_id, username, full_name)
    VALUES (?, ?, ?)
    """, (user_id, username, full_name))

    conn.commit()
    conn.close()


def save_application(user_id, role, fandom):
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE users
    SET role=?, fandom=?, status='pending'
    WHERE user_id=?
    """, (role, fandom, user_id))

    conn.commit()
    conn.close()


def update_status(user_id, status):
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET status=? WHERE user_id=?",
        (status, user_id)
    )

    conn.commit()
    conn.close()


def ban_user_db(user_id):
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE users SET banned=1 WHERE user_id=?",
        (user_id,)
    )

    conn.commit()
    conn.close()


def is_banned(user_id):
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT banned FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()
    conn.close()

    return bool(row and row[0])


def get_stats():
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE status='accepted'")
    accepted = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE status='pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = cursor.fetchone()[0]

    conn.close()

    return total, accepted, pending, banned


def get_users():
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]

    conn.close()

    return users


@dp.message(CommandStart())
async def start(message: Message):
    user = message.from_user

    add_user(
        user.id,
        f"@{user.username}" if user.username else "Нет username",
        user.full_name
    )

    if is_banned(user.id):
        await message.answer("⛔ Вы заблокированы.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Инфо-канал",
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

    await message.answer(
        "Добро пожаловать в ALLFANDS FLUD.\n\n"
        "Ознакомьтесь с инфо-каналом.",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "read_info")
async def read_info(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "❓ Контрольный вопрос:\n\nМаксимальный срок реста?"
    )

    await state.set_state(Registration.question)
    await callback.answer()


@dp.message(Registration.question)
async def question_check(message: Message, state: FSMContext):
    if message.text.lower().strip() != "3 недели":
        await message.answer(
            "❌ Неверный ответ. Попробуйте ещё раз."
        )
        return

    await message.answer("🎭 Напишите вашу роль:")
    await state.set_state(Registration.role)


@dp.message(Registration.role)
async def get_role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)

    await message.answer(
        "🌍 Напишите ваш основной фандом:"
    )

    await state.set_state(Registration.fandom)


@dp.message(Registration.fandom)
async def get_fandom(message: Message, state: FSMContext):
    data = await state.get_data()

    role = data["role"]
    fandom = message.text

    user = message.from_user

    save_application(
        user.id,
        role,
        fandom
    )

    username = (
        f"@{user.username}"
        if user.username
        else "Не указан"
    )

    text = (
        "📨 Новая заявка\n\n"
        f"👤 Username: {username}\n"
        f"📛 Имя: {user.full_name}\n"
        f"🆔 ID: {user.id}\n\n"
        f"🎭 Роль: {role}\n"
        f"🌍 Фандом: {fandom}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"accept_{user.id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject_{user.id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⛔ Бан",
                    callback_data=f"ban_{user.id}"
                )
            ]
        ]
    )

    for admin in ADMINS:
        try:
            await bot.send_message(
                admin,
                text,
                reply_markup=keyboard
            )
        except:
            pass

    await message.answer(
        "✅ Заявка отправлена администрации."
    )

    await state.clear()


@dp.callback_query(F.data.startswith("accept_"))
async def accept_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split("_")[1])

    update_status(user_id, "accepted")

    try:
        await bot.send_message(
            user_id,
            f"🎉 Ваша заявка одобрена!\n\n"
            f"Ссылка на флуд:\n{FLUD_LINK}"
        )
    except:
        pass

    await callback.answer("Одобрено")


@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split("_")[1])

    update_status(user_id, "rejected")

    try:
        await bot.send_message(
            user_id,
            "❌ Ваша заявка отклонена."
        )
    except:
        pass

    await callback.answer("Отклонено")


@dp.callback_query(F.data.startswith("ban_"))
async def ban_user_callback(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split("_")[1])

    ban_user_db(user_id)

    try:
        await bot.send_message(
            user_id,
            "⛔ Вы были заблокированы."
        )
    except:
        pass

    await callback.answer("Пользователь забанен")


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMINS:
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📨 Рассылка",
                    callback_data="mailing"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="users"
                )
            ]
        ]
    )

    await message.answer(
        "🔐 Админ-панель",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    total, accepted, pending, banned = get_stats()

    await callback.message.answer(
        f"📊 Статистика\n\n"
        f"Всего: {total}\n"
        f"Одобрено: {accepted}\n"
        f"Ожидают: {pending}\n"
        f"Забанено: {banned}"
    )

    await callback.answer()


@dp.callback_query(F.data == "users")
async def users_list(callback: CallbackQuery):
    if callback.from_user.id not in ADMINS:
        return

    users = get_users()

    if not users:
        await callback.message.answer("Нет пользователей.")
        return

    text = "👥 Пользователи:\n\n"

    for user_id in users[:200]:
        text += f"{user_id}\n"

    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data == "mailing")
async def mailing(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMINS:
        return

    await callback.message.answer(
        "Введите текст рассылки:"
    )

    await state.set_state(Mailing.text)
    await callback.answer()


@dp.message(Mailing.text)
async def mailing_send(message: Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        return

    users = get_users()

    sent = 0

    for user_id in users:
        try:
            await bot.send_message(
                user_id,
                message.text
            )
            sent += 1
        except:
            pass

    await message.answer(
        f"✅ Рассылка завершена.\nОтправлено: {sent}"
    )

    await state.clear()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    asyncio.run(main())