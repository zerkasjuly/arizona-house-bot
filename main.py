import os
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
MSK = timezone(timedelta(hours=3))

records = []
jobs = {}

SERVERS = {
    "07": "Mesa",
    "14": "Winslow",
    "15": "Payson",
    "20": "Sun-City"
}


# =========================
# TIME HELPERS
# =========================

def now():
    return datetime.now(MSK)


def next_payday(dt):
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


# =========================
# 🔥 ГЛАВНАЯ ФУНКЦИЯ РАСЧЁТА
# =========================

def calc_drop_from_find(payday_left: int):
    """
    payday_left = число из /find (ОСТАЛОСЬ payday)
    """

    base = next_payday(now())  # ближайший payday

    drop = base + timedelta(hours=payday_left)

    return drop


# =========================
# RECORD MODEL
# =========================

def create_record(obj_id, server, payday_left):
    drop = calc_drop_from_find(payday_left)

    return {
        "id": obj_id,
        "server": server,
        "payday_left": payday_left,
        "drop": drop
    }


# =========================
# CLEANUP JOBS
# =========================

def cancel_jobs(obj_id):
    if obj_id in jobs:
        for job in jobs[obj_id]:
            job.schedule_removal()
        del jobs[obj_id]


def schedule(app, chat_id, rec):
    cancel_jobs(rec["id"])
    jobs[rec["id"]] = []

    sec = (rec["drop"] - now()).total_seconds()

    if sec > 0:
        jobs[rec["id"]].append(
            app.job_queue.run_once(
                notify,
                when=sec,
                chat_id=chat_id,
                data=rec
            )
        )


async def notify(context):
    d = context.job.data

    msg = (
        f"🚨 {d['id']} | {SERVERS[d['server']]}\n"
        f"⏳ СЛЁТ СЕЙЧАС"
    )

    await context.bot.send_message(context.job.chat_id, msg)


# =========================
# COMMANDS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Формат:\n"
        "/add ID SERVER PAYDAY_LEFT\n\n"
        "Пример:\n"
        "/add 1618 07 16"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        obj_id = context.args[0]
        server = context.args[1]
        payday_left = int(context.args[2])

        rec = create_record(obj_id, server, payday_left)
        records.append(rec)

        schedule(context.application, update.effective_chat.id, rec)

        await update.message.reply_text(
            f"✅ {obj_id} → слёт {rec['drop'].strftime('%d.%m %H:%M')}"
        )

    except:
        await update.message.reply_text("❌ формат: /add ID SERVER PAYDAY")


async def list_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not records:
        await update.message.reply_text("пусто")
        return

    msg = "🔥 СЛЁТЫ\n\n"

    for r in sorted(records, key=lambda x: x["drop"]):
        remaining = r["drop"] - now()
        h = int(remaining.total_seconds() // 3600)
        m = int((remaining.total_seconds() % 3600) // 60)

        msg += (
            f"🏠 {r['id']} | {SERVERS[r['server']]}\n"
            f"⏳ осталось: {h}ч {m}м\n"
            f"🚨 слёт: {r['drop'].strftime('%d.%m %H:%M')}\n\n"
        )

    await update.message.reply_text(msg)


# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_records))

    app.run_polling()


if __name__ == "__main__":
    main()
