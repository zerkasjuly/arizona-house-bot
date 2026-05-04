import os
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
MSK = timezone(timedelta(hours=3))

records = []
jobs = {}

SERVERS = {
    "03": "Scottdale",
    "07": "Mesa",
    "08": "Red-Rock",
    "10": "Surprise",
    "12": "Glendale",
    "14": "Winslow",
    "15": "Payson",
    "20": "Sun-City",
    "24": "Wednesday",
    "28": "Christmas",
    "29": "Mirage"
}

SERVER_OFFSET = {
    "03": 0,
    "07": 1,
    "08": 0,
    "10": 0,
    "12": 0,
    "14": 1,
    "15": 0,
    "20": 0,
    "24": 0,
    "28": 0,
    "29": 0
}


def now():
    return datetime.now(MSK)


def parse_start(st):
    dt = datetime.strptime(st, "%H:%M").replace(
        year=now().year,
        month=now().month,
        day=now().day,
        tzinfo=MSK
    )

    if dt > now():
        dt -= timedelta(days=1)

    return dt


def cancel_jobs(obj_id):
    if obj_id in jobs:
        for job in jobs[obj_id]:
            job.schedule_removal()
        del jobs[obj_id]


def get_step(insured):
    return 1 if insured else 2


def calc_drop(start, payday, server, insured):
    step = get_step(insured)
    offset = SERVER_OFFSET.get(server, 0)

    hours_left = (payday - offset) / step

    if hours_left < 0:
        hours_left = 0

    return parse_start(start) + timedelta(hours=hours_left)


def current_display(record):
    passed = int((now() - record["start"]).total_seconds() // 3600)

    left = record["start_payday"] - passed * get_step(record["insured"])

    return max(left, 0)


async def notify(context):
    d = context.job.data
    emoji = "🏠" if d["type"] == "house" else "🏢"

    await context.bot.send_message(
        context.job.chat_id,
        f"🚨 {emoji} №{d['id']} на сервере {SERVERS[d['server']]} слетает через {d['mins']} минут"
    )


async def cleanup(context):
    obj_id = context.job.data
    global records

    records = [r for r in records if r["id"] != obj_id]
    cancel_jobs(obj_id)


def schedule(app, chat_id, rec):
    cancel_jobs(rec["id"])
    jobs[rec["id"]] = []

    for mins in [10, 5]:
        sec = (rec["drop"] - now()).total_seconds() - mins * 60

        if sec > 0:
            job = app.job_queue.run_once(
                notify,
                when=sec,
                chat_id=chat_id,
                data={
                    "id": rec["id"],
                    "server": rec["server"],
                    "mins": mins,
                    "type": rec["type"]
                }
            )
            jobs[rec["id"]].append(job)

    sec = (rec["drop"] - now()).total_seconds()

    if sec > 0:
        jobs[rec["id"]].append(
            app.job_queue.run_once(cleanup, when=sec, data=rec["id"])
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/ah\n"
        "/ab\n"
        "/list\n"
        "/del ID\n"
        "/gone ID"
    )


async def add_object(update, context, obj_type):
    text = update.message.text.replace("/ah", "").replace("/ab", "").strip()
    lines = text.split("\n")
    out = []

    for line in lines:
        try:
            st, obj_id, pay, ins, server = line.split()

            insured = ins.lower() == "yes"

            rec = {
                "id": obj_id,
                "type": obj_type,
                "insured": insured,
                "server": server,
                "drop": calc_drop(st, int(pay), server, insured),
                "start": parse_start(st),
                "start_payday": int(pay)
            }

            records.append(rec)
            schedule(context.application, update.effective_chat.id, rec)

            out.append(f"✅ {obj_id} → {rec['drop'].strftime('%d.%m %H:%M')}")

        except:
            out.append(f"❌ {line}")

    await update.message.reply_text("\n".join(out))


async def add_house(update, context):
    await add_object(update, context, "house")


async def add_biz(update, context):
    await add_object(update, context, "biz")


async def delete_record(update, context):
    obj_id = context.args[0]

    global records
    records = [r for r in records if r["id"] != obj_id]
    cancel_jobs(obj_id)

    await update.message.reply_text(f"🗑 Удалён {obj_id}")


async def gone(update, context):
    obj_id = context.args[0]

    global records
    records = [r for r in records if r["id"] != obj_id]
    cancel_jobs(obj_id)

    await update.message.reply_text(f"✅ Подтверждён слёт {obj_id}")


async def list_records(update, context):
    global records
    records = [r for r in records if r["drop"] > now()]

    if not records:
        await update.message.reply_text("Список пуст")
        return

    msg = "🔥 Список слётов\n\n"

    for rec in sorted(records, key=lambda x: x["drop"]):
        emoji = "🏠" if rec["type"] == "house" else "🏢"
        shield = "🛡" if rec["insured"] else "❌"

        msg += (
            f"{emoji} {rec['id']} | {SERVERS[rec['server']]}\n"
            f"📊 Сейчас: {current_display(rec)} payday\n"
            f"🚨 Слёт: {rec['drop'].strftime('%d.%m %H:%M')}\n"
            f"{shield} {'Страховка' if rec['insured'] else 'Без страховки'}\n\n"
        )

    await update.message.reply_text(msg)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["ah", "addhouse"], add_house))
    app.add_handler(CommandHandler(["ab", "addbiz"], add_biz))
    app.add_handler(CommandHandler(["list"], list_records))
    app.add_handler(CommandHandler(["del"], delete_record))
    app.add_handler(CommandHandler(["gone"], gone))

    app.run_polling()


if __name__ == "__main__":
    main()
