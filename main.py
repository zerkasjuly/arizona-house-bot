import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)
import os

TOKEN = os.getenv("BOT_TOKEN")

# ---------- TIME ----------
def now_msk():
    return datetime.utcnow() + timedelta(hours=3)

# ---------- SERVERS ----------
SERVER_NAMES = {
    "mesa": "Mesa", "phoenix": "Phoenix", "tucson": "Tucson",
    "scottdale": "Scottdale", "chandler": "Chandler",
    "brainburg": "BrainBurg", "saint rose": "Saint Rose",
    "red-rock": "Red-Rock", "red rock": "Red-Rock",
    "yuma": "Yuma", "surprise": "Surprise", "prescott": "Prescott",
    "glendale": "Glendale", "kingman": "Kingman",
    "winslow": "Winslow", "payson": "Payson", "gilbert": "Gilbert",
    "show-low": "Show-Low", "show low": "Show-Low",
    "casa-grande": "Casa-Grande", "casa grande": "Casa-Grande",
    "page": "Page", "sun-city": "Sun-City", "sun city": "Sun-City",
    "queen-creek": "Queen-Creek", "queen creek": "Queen-Creek",
    "sedona": "Sedona", "holiday": "Holiday", "wednesday": "Wednesday",
    "yava": "Yava", "faraway": "Faraway", "bumble bee": "Bumble Bee",
    "christmas": "Christmas", "mirage": "Mirage",
    "love": "Love", "drake": "Drake", "space": "Space"
}

def normalize_server(name):
    return SERVER_NAMES.get(name.lower(), name.title())

# ---------- DB ----------
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

# ---------- CALC ----------
def calc_time(payday, safe):
    real = payday - 1 if safe else payday
    return now_msk() + timedelta(hours=max(real, 1))

# ---------- NOTIFY ----------
async def notify(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    hid, text = job.data.split("|")
    await context.bot.send_message(job.chat_id, f"🏠 Дом {hid}\n{text}")

# ---------- SCHEDULE ----------
def schedule(job_queue, chat_id, hid, payday, safe):
    drop = calc_time(payday, safe)
    seconds = (drop - now_msk()).total_seconds()

    if seconds <= 0:
        return

    alerts = [(seconds-600, "⏰ 10 мин"), (seconds-300, "⏰ 5 мин")]

    for delay, txt in alerts:
        if delay > 0:
            job_queue.run_once(
                notify, delay,
                chat_id=chat_id,
                data=f"{hid}|{txt}"
            )

# ---------- RESTORE ----------
async def restore_jobs(app):
    cur.execute("SELECT * FROM houses")
    for hid, payday, safe, server in cur.fetchall():
        for chat_id in app.chat_data:
            schedule(app.job_queue, chat_id, hid, payday, safe)

# ---------- PARSER ----------
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    lines = text.split("\n")

    added = []

    for line in lines:
        parts = line.split()
        if len(parts) < 4:
            continue

        try:
            hid = int(parts[0])
            payday = int(parts[1])
            server = normalize_server(parts[-1])
            safe = 1 if "со страховкой" in line else 0

            cur.execute(
                "REPLACE INTO houses VALUES (?, ?, ?, ?)",
                (hid, payday, safe, server)
            )

            schedule(context.job_queue, update.effective_chat.id, hid, payday, safe)
            added.append(f"{hid} ({server})")
        except:
            pass

    conn.commit()

    if added:
        msg = "✅ Добавлены:\n" + "\n".join(f"• {a}" for a in added)
        await update.message.reply_text(msg)

# ---------- LIST ----------
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Пусто")
        return

    data = []
    for hid, payday, safe, server in rows:
        drop = calc_time(payday, safe)
        data.append((drop, hid, safe, server))

    data.sort(key=lambda x: x[0])

    text = "🏠 Дома:\n\n"
    keyboard = []

    for drop, hid, safe, server in data:
        text += f"{hid} | {server} | {'🛡' if safe else '❌'} | {drop.strftime('%H:%M')}\n"
        keyboard.append([InlineKeyboardButton(f"❌ {hid}", callback_data=f"del_{hid}")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ---------- BUTTON DELETE ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("del_"):
        hid = int(query.data.split("_")[1])
        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()
        await query.edit_message_text(f"❌ Дом {hid} удалён")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Бот домов\n\n"
        "Можно вставлять несколько домов:\n"
        "123 3 со страховкой Mesa\n"
        "456 5 без страховки Phoenix\n\n"
        "/list — список"
    )

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))
    app.add_handler(CallbackQueryHandler(button_handler))

    app.post_init = restore_jobs

    app.run_polling()

if __name__ == "__main__":
    main()
