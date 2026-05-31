from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
import asyncio
import os

TOKEN = os.getenv("TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📖 О флуде", callback_data="about")],
            [InlineKeyboardButton(text="📢 Инфо-канал", callback_data="channel")],
            [InlineKeyboardButton(text="👥 Администрация", callback_data="admins")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton(text="🚪 Вступить во флуд", callback_data="join")]
        ]
    )

    await message.answer(
        "Добро пожаловать в ALLFANDS FLUD.\n\nВыберите интересующий раздел:",
        reply_markup=keyboard
    )


@dp.callback_query(F.data == "about")
async def about(callback: CallbackQuery):
    await callback.message.answer(
        "ALLFANDS FLUD — сообщество для общения, знакомств и приятного времяпровождения.\n\n"
        "Флуд существует уже почти год и продолжает развиваться."
    )


@dp.callback_query(F.data == "channel")
async def channel(callback: CallbackQuery):
    await callback.message.answer(
        "📢 Информационный канал:\n\nhttps://t.me/+rFs7nnx639BmNzgy"
    )


@dp.callback_query(F.data == "admins")
async def admins(callback: CallbackQuery):
    await callback.message.answer(
        "👥 Администрация\n\n"
        "Основатель: @winsvkk\n"
        "Администратор: @sultee_ss"
    )


@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    await callback.message.answer(
        "📊 Статистика\n\n"
        "Возраст флуда: почти 1 год"
    )


@dp.callback_query(F.data == "join")
async def join(callback: CallbackQuery):
    await callback.message.answer(
        "🚪 Ссылка для вступления:\n\nhttps://t.me/+zTukwrwrqlgxOGUy"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())