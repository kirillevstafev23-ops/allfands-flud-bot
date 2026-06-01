import asyncio
import logging
import random
import os
from datetime import datetime
from contextlib import closing
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ---------------- CONFIG IMPORT ----------------
# если у тебя есть config_example.py — лучше потом переименовать в config.py
try:
    from config_example import TOKEN, ADMINS, INFO_CHANNEL, FLUD_LINK, FLUD_CHAT_ID
except:
    TOKEN = os.getenv("TOKEN")
    ADMINS = [1739947062, 5655991466]
    INFO_CHANNEL = "https://t.me/+example"
    FLUD_LINK = "https://t.me/+example"
    FLUD_CHAT_ID = -1000000000

# ---------------- LOGGING ----------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# ---------------- DB ----------------

def db():
    return sqlite3.connect("flud.db", check_same_thread=False)


def init_db():
    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT,
            fandom TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS applications(
            user_id INTEGER PRIMARY KEY,
            msg_admin_1 INTEGER,
            msg_admin_2 INTEGER
        )
        """)

        conn.commit()


def now():
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def save_user(user_id, username):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO users(user_id, username, created_at)
        VALUES (?, ?, ?)
        """, (user_id, username, now()))
        conn.commit()


def update_profile(user_id, role, fandom):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("""
        UPDATE users SET role=?, fandom=?, status='pending'
        WHERE user_id=?
        """, (role, fandom, user_id))
        conn.commit()


def get_status(user_id):
    with closing(db()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None

# ---------------- FSM ----------------

class Register(StatesGroup):
    question = State()
    role = State()
    fandom = State()

# ---------------- KEYBOARDS ----------------

def info_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Инфо-канал", url=INFO_CHANNEL)],
        [InlineKeyboardButton(text="✅ Начать", callback_data="start_form")]
    ])

# ---------------- START ----------------

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    save_user(
        message.from_user.id,
        f"@{message.from_user.username}" if message.from_user.username else "no_username"
    )

    if get_status(message.from_user.id) == "banned":
        await message.answer("🚫 Вы заблокированы.")
        return

    await state.clear()

    await message.answer(
        "✨ Добро пожаловать\n\n" + random.choice([
            "История начинается здесь.",
            "Каждое сообщение важно."
        ]),
        reply_markup=info_kb()
    )

# ---------------- FLOW ----------------

@dp.callback_query(F.data == "start_form")
async def start_form(call: CallbackQuery, state: FSMContext):
    await state.set_state(Register.question)
    await call.message.answer("❓ Сколько длится рест?")
    await call.answer()


@dp.message(Register.question)
async def q(message: Message, state: FSMContext):
    if message.text.lower().strip() != "3 недели":
        await message.answer("🚫 Неверно")
        return

    await state.set_state(Register.role)
    await message.answer("🎭 Ваша роль?")


@dp.message(Register.role)
async def role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(Register.fandom)
    await message.answer("🌍 Ваш фандом?")


@dp.message(Register.fandom)
async def fandom(message: Message, state: FSMContext):
    data = await state.get_data()

    role = data["role"]
    fandom = message.text

    update_profile(message.from_user.id, role, fandom)

    text = f"""
📨 Новая заявка

👤 @{message.from_user.username or "no_username"}
🆔 {message.from_user.id}
🎭 {role}
🌍 {fandom}
🕰 {now()}
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept:{message.from_user.id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{message.from_user.id}")],
        [InlineKeyboardButton(text="🚫 Бан", callback_data=f"ban:{message.from_user.id}")]
    ])

    for admin in ADMINS:
        await bot.send_message(admin, text, reply_markup=kb)

    await message.answer("📨 Заявка отправлена")
    await state.clear()

# ---------------- ADMIN ----------------

@dp.callback_query(F.data.startswith("accept:"))
async def accept(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    user_id = int(call.data.split(":")[1])

    await bot.send_message(user_id, f"✨ Одобрено\n\n{FLUD_LINK}")
    await call.message.edit_text("✅ Принято")
    await call.answer()


@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    user_id = int(call.data.split(":")[1])

    await bot.send_message(user_id, "❌ Отклонено")
    await call.message.edit_text("❌ Отклонено")
    await call.answer()


@dp.callback_query(F.data.startswith("ban:"))
async def ban(call: CallbackQuery):
    if call.from_user.id not in ADMINS:
        return

    user_id = int(call.data.split(":")[1])

    await bot.send_message(user_id, "🚫 Забанен")
    await call.message.edit_text("🚫 Бан")
    await call.answer()

# ---------------- MAIN ----------------

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
