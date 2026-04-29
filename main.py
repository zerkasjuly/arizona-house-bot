import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import os

TOKEN = os.getenv("BOT_TOKEN")

# ---------- МСК ----------
def now_msk():
    return datetime.utcnow() + timedelta(hours=3)


# ---------- DB ----------
conn = sqlite3.connect("houses.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS houses (
    id INTEGER PRIMARY KEY,
    payday INTEGER,
    safe INTEGER
)
""")
conn.commit()


# ---------- CALC ----------
def calc_time(payday, safe):
    real = payday - 1 if safe else payday
    real = max(real, 1)
    return now_msk() + timedelta(hours=real)


# ---------- NOTIFY ----------
async def notify_custom(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    house_id, text = job.data.split("|")

    await context.bot.send_message(
        job.chat_id,
        f"🏠 Дом {house_id}\n{text}"
    )


# ---------- SCHEDULER ----------
def schedule(job_queue, chat_id, house_id, payday, safe):
    drop = calc_time(payday, safe)

    now = now_msk()
    seconds_left = (drop - now).total_seconds()

    if seconds_left <= 0:
        return

    alerts = [
        (seconds_left - 600, "⏰ 10 минут до слёта"),
        (seconds_left - 300, "⏰ 5 минут до слёта"),
    ]

    for delay, text in alerts:
        if delay > 0:
            job_queue.run_once(
                notify_custom,
                delay,
                chat_id=chat_id,
                data=f"{house_id}|{text}"
            )


# ---------- AUTO REFRESH ----------
async def refresh_loop(app):
    while True:
        await asyncio.sleep(300)  # каждые 5 минут

        cur.execute("SELECT * FROM houses")
        rows = cur.fetchall()

        for hid, payday, safe in rows:
            for chat_id in app.chat_data:
                schedule(app.job_queue, chat_id, hid, payday, safe)


# ---------- ADD ----------
async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hid = int(context.args[0])
        payday = int(context.args[1])
        mode = context.args[2].lower()

        safe = 1 if mode == "safe" else 0

        cur.execute("REPLACE INTO houses VALUES (?, ?, ?)", (hid, payday, safe))
        conn.commit()

        schedule(context.job_queue, update.effective_chat.id, hid, payday, safe)

        await update.message.reply_text(
            f"🏠 Дом {hid} добавлен\n"
            f"{'🛡 страховка' if safe else '❌ без'}\n"
            f"Слёт: {calc_time(payday, safe).strftime('%H:%M')} МСК"
        )

    except:
        await update.message.reply_text("Используй: /add 123 3 safe/no")


# ---------- LIST ----------
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Список пуст")
        return

    text = "🏠 Дома:\n\n"

    for hid, payday, safe in rows:
        drop = calc_time(payday, safe)
        text += f"{hid} | {'🛡' if safe else '❌'} | {drop.strftime('%H:%M')}\n"

    await update.message.reply_text(text)


# ---------- DELETE ----------
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hid = int(context.args[0])
        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()
        await update.message.reply_text(f"Удалён {hid}")
    except:
        await update.message.reply_text("Используй: /del 123")


# ---------- TEXT PARSER ----------
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    if "слетит через" in text:
        try:
            parts = text.split()
            payday = int(parts[2])
            safe = 1 if "страх" in text else 0

            drop = calc_time(payday, safe)

            await update.message.reply_text(
                f"📌 Считаю...\n"
                f"Слёт: {drop.strftime('%H:%M')} МСК\n"
                f"{'🛡 страховка учтена' if safe else '❌ без страховки'}"
            )
        except:
            pass


# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/add id payday safe/no\n"
        "/list\n"
        "/del id\n\n"
        "Пиши: 'слетит через 3 payday'"
    )


# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_houses))
    app.add_handler(CommandHandler("del", delete))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))

    app.run_polling()


if __name__ == "__main__":
    main()
