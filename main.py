"""
Запускает оба бота параллельно:
  - bot.py (пациентский бот @med_st)
  - admin_bot.py (бот врача)
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, ADMIN_BOT_TOKEN
from firebase_db import init_firebase
from handlers import router
from admin_bot import admin_router
from scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def run_patient_bot():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await start_scheduler(bot)
    logger.info("Бот для пациентов запущен ✅")
    await dp.start_polling(bot, skip_updates=True)


async def run_admin_bot():
    bot = Bot(token=ADMIN_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin_router)
    logger.info("Бот врача запущен ✅")
    await dp.start_polling(bot, skip_updates=True)


async def main():
    init_firebase()
    # Запускаем оба бота параллельно
    await asyncio.gather(
        run_patient_bot(),
        run_admin_bot()
    )


if __name__ == "__main__":
    asyncio.run(main())
