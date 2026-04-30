import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import os

TOKEN = os.getenv("BOT_TOKEN")

# ---------- МСК ----------
def now_msk():
    return datetime.utcnow() + timedelta(hours=3)

# ---------- СЕРВЕРА ARIZONA RP ----------
SERVER_NAMES = {
    "phoenix": "Phoenix",
    "tucson": "Tucson",
    "scottdale": "Scottdale",
    "chandler": "Chandler",
    "brainburg": "BrainBurg",
    "saint rose": "Saint Rose",
    "mesa": "Mesa",
    "red-rock": "Red-Rock",
    "red rock": "Red-Rock",
    "yuma": "Yuma",
    "surprise": "Surprise",
    "prescott": "Prescott",
    "glendale": "Glendale",
    "kingman": "Kingman",
    "winslow": "Winslow",
    "payson": "Payson",
    "gilbert": "Gilbert",
    "show-low": "Show-Low",
    "show low": "Show-Low",
    "casa-grande": "Casa-Grande",
    "casa grande": "Casa-Grande",
    "page": "Page",
    "sun-city": "Sun-City",
    "sun city": "Sun-City",
    "queen-creek": "Queen-Creek",
    "queen creek": "Queen-Creek",
    "sedona": "Sedona",
    "holiday": "Holiday",
    "wednesday": "Wednesday",
    "yava": "Yava",
    "faraway": "Faraway",
    "bumble bee": "Bumble Bee",
    "christmas": "Christmas",
    "mirage": "Mirage",
    "love": "Love",
    "drake": "Drake",
    "space": "Space"
}

def normalize_server(name):
    name = name.lower()
    return SERVER_NAMES.get(name, name.title())

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
    real = max(real, 1)
    return now_msk() + timedelta(hours=real)

# ---------- NOTIFY ----------
async def notify(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    house_id, text = job.data.split("|")

    await context.bot.send_message(
        job.chat_id,
        f"🏠 House {house_id}\n{text}"
    )

# ---------- SCHEDULE ----------
def schedule(job_queue, chat_id, house_id, payday, safe):
    drop = calc_time(payday, safe)
    now = now_msk()
    seconds_left = (drop - now).total_seconds()

    if seconds_left <= 0:
        return

    alerts = [
        (seconds_left - 600, "⏰ 10 minutes before drop"),
        (seconds_left - 300, "⏰ 5 minutes before drop"),
    ]

    for delay, text in alerts:
        if delay > 0:
            job_queue.run_once(
                notify,
                delay,
                chat_id=chat_id,
                data=f"{house_id}|{text}"
            )

# ---------- AUTO ADD ----------
async def parser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower().strip()
    parts = text.split()

    if len(parts) >= 4:
        try:
            hid = int(parts[0])
            payday = int(parts[1])
            server_raw = parts[-1]

            mode = " ".join(parts[2:-1])
            safe = 1 if "со страховкой" in mode else 0

            server = normalize_server(server_raw)

            cur.execute(
                "REPLACE INTO houses VALUES (?, ?, ?, ?)",
                (hid, payday, safe, server)
            )
            conn.commit()

            schedule(context.job_queue, update.effective_chat.id, hid, payday, safe)

            await update.message.reply_text(
                f"✅ Дом {hid} добавлен\n"
                f"🖥 Сервер: {server}\n"
                f"{'🛡 со страховкой' if safe else '❌ без страховки'}\n"
                f"⏰ Слёт: {calc_time(payday, safe).strftime('%H:%M')} МСК"
            )
            return
        except:
            pass

# ---------- LIST ----------
async def list_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cur.execute("SELECT * FROM houses")
    rows = cur.fetchall()

    if not rows:
        await update.message.reply_text("Список пуст")
        return

    data = []

    for hid, payday, safe, server in rows:
        drop = calc_time(payday, safe)
        data.append((drop, hid, payday, safe, server))

    data.sort(key=lambda x: x[0])

    text = "🏠 Дома (по ближайшему слёту):\n\n"

    for drop, hid, payday, safe, server in data:
        text += (
            f"🏠 {hid} | 🖥 {server} | "
            f"{'🛡' if safe else '❌'} | "
            f"{drop.strftime('%H:%M')}\n"
        )

    await update.message.reply_text(text)

# ---------- SERVER ----------
async def server_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        server_input = context.args[0]
        server = normalize_server(server_input)

        cur.execute("SELECT * FROM houses WHERE server=?", (server,))
        rows = cur.fetchall()

        if not rows:
            await update.message.reply_text("Пусто")
            return

        data = []

        for hid, payday, safe, srv in rows:
            drop = calc_time(payday, safe)
            data.append((drop, hid, safe))

        data.sort(key=lambda x: x[0])

        text = f"🖥 Сервер {server}:\n\n"

        for drop, hid, safe in data:
            text += f"{hid} | {'🛡' if safe else '❌'} | {drop.strftime('%H:%M')}\n"

        await update.message.reply_text(text)

    except:
        await update.message.reply_text("Используй: /server Mesa")

# ---------- DELETE ----------
async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hid = int(context.args[0])
        cur.execute("DELETE FROM houses WHERE id=?", (hid,))
        conn.commit()
        await update.message.reply_text(f"Удалён {hid}")
    except:
        await update.message.reply_text("Используй: /del 123")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Бот домов\n\n"
        "Пример:\n"
        "123 3 со страховкой Mesa\n"
        "123 3 без страховки Red-Rock\n\n"
        "/list - список\n"
        "/server Mesa - фильтр\n"
        "/del 123 - удалить"
    )

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_houses))
    app.add_handler(CommandHandler("server", server_view))
    app.add_handler(CommandHandler("del", delete))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, parser))

    app.run_polling()

if __name__ == "__main__":
    main()
