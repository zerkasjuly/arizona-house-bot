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

# =========================
# 🌍 TIMEZONE (МСК / КИЕВ)
# =========================
TZ = ZoneInfo("Europe/Moscow")
# TZ = ZoneInfo("Europe/Kyiv")


# =========================
# ⏰ ТЕКУЩЕЕ ВРЕМЯ (БЕЗ МИНУТ)
# =========================
def now():
    n = datetime.now(TZ)
    return n.replace(minute=0, second=0, microsecond=0)


# =========================
# DB
# =========================
conn = sqlite3.connect("houses.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS houses (
    id INTEGER PRIMARY KEY,
    payday INTEGER,
    safe INTEGER,
    server TEXT
)
""")
conn.commit()


# =========================
# SIMULATION (ТОЛЬКО -1 / -2)
# =========================
def simulate_hours(payday: int, safe: int) -> int:
    hours = 0
    p = payday

    if safe:
        while p > 1:
            p -= 1
            hours += 1
        hours += 1
    else:
        while p > 0:
            p -= 2
            hours += 1

    return hours


# =========================
# DROP TIME
# =========================
def drop_time(payday, safe):
    return now() + timedelta(hours=simulate_hours(payday, safe))


# =========================
# PARSER
# =========================
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().split()

    if len(text) >= 4:
        try:
            hid = int(text[0])
            payday = int(text[1])
            server = text[-1]
            safe = 1 if "со" in " ".join(text[2:-1]) else 0

            cur.execute(
                "REPLACE INTO houses VALUES (?, ?, ?, ?)",
                (hid, payday, safe, server)
            )
            conn.commit()

            dt = drop_time(payday, safe)

            await update.message.reply_text(
                f"🏠 {hid} | {server}\n⏰ слёт: {dt.strftime('%H:%M')}"
            )
        except:
            pass


# =========================
# LIST
# =========================
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    data = []

    for hid, payday, safe, server in rows:
        dt = drop_time(payday, safe)
        hours_left = (dt - now()).total_seconds() / 3600

        data.append((dt, hid, server, hours_left))

    data.sort(key=lambda x: x[0])

    text = "🏠 Дома (по ближайшему слёту):\n\n"

    for dt, hid, server, hours_left in data:

        if hours_left <= 2:
            color = "🔴"
        elif hours_left <= 5:
            color = "🟡"
        else:
            color = "🟢"

        text += (
            f"{color} {hid} | {server} → {dt.strftime('%H:%M')}\n"
            f"⏳ ~{int(hours_left)}ч\n\n"
        )

    await update.message.reply_text(text)


# =========================
# DELETE
# =========================
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hid = int(context.args[0])
        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()
        await update.message.reply_text(f"Удалён {hid}")
    except:
        await update.message.reply_text("формат: /del 1234")


# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 FINAL BOT READY\n\n"
        "формат:\n"
        "1234 10 со страховкой mesa\n\n"
        "/list"
    )


# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))
    app.add_handler(CommandHandler("del", delete))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))

    app.run_polling()


if __name__ == "__main__":
    main()
