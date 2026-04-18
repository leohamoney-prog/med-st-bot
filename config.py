import os
from dotenv import load_dotenv
load_dotenv()

# ── Бот для пациентов ─────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN", "ТОКЕН_БОТА_ДЛЯ_ПАЦИЕНТОВ")

# ── Бот для врача ─────────────────────────────────────────────────
ADMIN_BOT_TOKEN  = os.getenv("ADMIN_BOT_TOKEN", "ТОКЕН_БОТА_ДЛЯ_ВРАЧА")
ADMIN_CHAT_ID    = int(os.getenv("ADMIN_CHAT_ID", "0"))  # твой Telegram ID

# ── Firebase ──────────────────────────────────────────────────────
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS", "")

# ── Напоминания ───────────────────────────────────────────────────
REMINDER_HOUR = 10  # в 10:00 по МСК отправлять напоминания
