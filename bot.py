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
from aiogram.filters import CommandStart
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


class Registration(StatesGroup):
    role = State()
    fandom = State()


def save_user(user_id, username, role, fandom):
    conn = sqlite3.connect("flud.db")
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR REPLACE INTO users
    (user_id, username, role, fandom, status)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, role, fandom, "pending"))

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


@dp.message(CommandStart())
async def start(message: Message):

    keyboard = InlineKeyboardMarkup(
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

    await message.answer(
        "Добро пожаловать в ALLFANDS FLUD.\n\n"
        "Перед вступлением обязательно ознакомьтесь с инфо-каналом.",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "read_info")
async def read_info(callback: CallbackQuery, state: FSMContext):

    await callback.message.answer(
        "🎭 Напишите вашу роль:"
    )

    await state.set_state(Registration.role)


@dp.message(Registration.role)
async def get_role(message: Message, state: FSMContext):

    await state.update_data(role=message.text)

    await message.answer(
        "🌍 Теперь напишите ваш основной фандом:"
    )

    await state.set_state(Registration.fandom)


@dp.message(Registration.fandom)
async def get_fandom(message: Message, state: FSMContext):

    data = await state.get_data()

    role = data["role"]
    fandom = message.text

    user = message.from_user

    save_user(
        user.id,
        user.username,
        role,
        fandom
    )

    text = (
        f"📨 Новая заявка\n\n"
        f"👤 Пользователь: @{user.username}\n"
        f"🆔 ID: {user.id}\n\n"
        f"🎭 Роль: {role}\n"
        f"🌍 Фандом: {fandom}"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принять",
                    callback_data=f"accept_{user.id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject_{user.id}"
                )
            ]
        ]
    )

    for admin in ADMINS:
        await bot.send_message(
            admin,
            text,
            reply_markup=keyboard
        )

    await message.answer(
        "✅ Ваша заявка отправлена администрации.\n\n"
        "Ожидайте решения."
    )

    await state.clear()


@dp.callback_query(F.data.startswith("accept_"))
async def accept_user(callback: CallbackQuery):

    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split("_")[1])

    update_status(user_id, "accepted")

    await bot.send_message(
        user_id,
        f"🎉 Ваша заявка одобрена!\n\n"
        f"Ссылка на флуд:\n{FLUD_LINK}"
    )

    await callback.answer("Пользователь принят")


@dp.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):

    if callback.from_user.id not in ADMINS:
        return

    user_id = int(callback.data.split("_")[1])

    update_status(user_id, "rejected")

    await bot.send_message(
        user_id,
        "❌ Ваша заявка была отклонена."
    )

    await callback.answer("Пользователь отклонён")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(main())