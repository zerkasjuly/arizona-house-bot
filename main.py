import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.getenv("BOT_TOKEN")

TZ = ZoneInfo("Europe/Moscow")


# =========================
# TIME PARSE
# =========================
def parse_time(t: str):
    h, m = map(int, t.split(":"))
    return datetime.now(TZ).replace(hour=h, minute=0, second=0, microsecond=0)


# =========================
# SIMULATION FIXED
# =========================
def calc_hours(payday: int, safe: int):
    if safe:
        return payday - 1
    else:
        # ❗ ВАЖНОЕ ИСПРАВЛЕНИЕ
        # (-2 шагами, слёт на 1)
        return (payday - 1 + 1) // 2


# =========================
# PARSER (НОВЫЙ ФОРМАТ)
# =========================
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text.lower()

        # формат:
        # 05:00 / 1111 / 3 / без / phoenix
        parts = [x.strip() for x in text.split("/")]

        if len(parts) < 5:
            return

        t = parse_time(parts[0])
        hid = int(parts[1])
        payday = int(parts[2])
        mode = parts[3]
        server = parts[4]

        safe = 1 if "со" in mode else 0

        hours = calc_hours(payday, safe)

        drop = t + timedelta(hours=hours)

        await update.message.reply_text(
            f"🏠 {hid} | {server}\n⏰ слёт: {drop.strftime('%H:%M')}"
        )

    except:
        pass


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ФОРМАТ:\n"
        "05:00 / 1111 / 3 / без страховки / phoenix\n\n"
        "/list пока отключен в этой версии"
    )


# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))

    app.run_polling()


if __name__ == "__main__":
    main()
