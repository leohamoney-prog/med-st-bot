import asyncio
import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import REMINDER_HOUR
from firebase_db import get_appointments_for_reminder, mark_notified
from keyboards import attendance_kb
from utils import fmt_date, tomorrow_str

logger = logging.getLogger(__name__)


async def send_reminders(bot: Bot):
    tomorrow = tomorrow_str()
    appointments = await get_appointments_for_reminder(tomorrow)
    logger.info(f"Напоминания на {tomorrow}: {len(appointments)} шт.")
    for appt in appointments:
        tg_id = appt.get("tgId")
        if not tg_id:
            continue
        try:
            await bot.send_message(
                tg_id,
                f"🦷 <b>Напоминание о приёме!</b>\n\n"
                f"Завтра, <b>{fmt_date(appt['date'])}</b> в <b>{appt['time']}</b>\n"
                f"📋 {appt.get('service','')}\n\n"
                f"Вы придёте на приём?",
                parse_mode="HTML",
                reply_markup=attendance_kb(appt["id"])
            )
            await mark_notified(appt["id"])
        except Exception as e:
            logger.error(f"Ошибка напоминания {appt['id']}: {e}")
        await asyncio.sleep(0.1)


async def start_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        send_reminders,
        trigger="cron",
        hour=REMINDER_HOUR,
        minute=0,
        args=[bot],
        id="reminders",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Планировщик запущен ✅ (напоминания в {REMINDER_HOUR}:00 МСК)")
