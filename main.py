import os
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
MSK = timezone(timedelta(hours=3))

records = []
jobs = {}

HOUSE_LIMIT = 104000
BIZ_LIMIT = 250000

SERVERS = {
    "07": "Mesa",
    "14": "Winslow",
    "15": "Payson",
    "20": "Sun-City"
}

HOUSE_TAX = {
    "07": 1000,
    "14": 1000,
    "15": 619,
    "20": 700
}

BIZ_TAX = {
    "07": 2000,
    "14": 3500,
    "15": 1489,
    "20": 1350
}

SERVER_OFFSET = {
    "07": 1,
    "14": 1,
    "15": 0,
    "20": 0
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


def get_tax(server, obj_type, insured):
    tax = HOUSE_TAX[server] if obj_type == "house" else BIZ_TAX[server]
    return tax / 2 if insured else tax


def calc_drop(start, payday, server, obj_type, insured):
    tax = get_tax(server, obj_type, insured)
    limit = HOUSE_LIMIT if obj_type == "house" else BIZ_LIMIT
    offset = SERVER_OFFSET.get(server, 0)

    current_tax = limit - ((payday - offset) * tax)
    current = parse_start(start)

    while current_tax < limit:
        current += timedelta(hours=1)
        current_tax += tax

    return current


def current_tax(record):
    passed = int((now() - record["start"]).total_seconds() // 3600)
    tax = get_tax(record["server"], record["type"], record["insured"])

    total = record["base_tax"] + passed * tax
    limit = HOUSE_LIMIT if record["type"] == "house" else BIZ_LIMIT

    if total > limit:
        total = limit

    return int(total), limit


async def notify(context):
    d = context.job.data
    emoji = "🏠" if d["type"] == "house" else "🏢"

    msg = (
        f"🚨 {emoji} №{d['id']} "
        f"на сервере {SERVERS[d['server']]} "
        f"слетает через {d['mins']} минут"
    )

    await context.bot.send_message(context.job.chat_id, msg)


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
        "/ah /addhouse\n"
        "/ab /addbiz\n"
        "/list\n"
        "/del\n"
        "/gone"
    )


async def add_object(update, context, obj_type):
    text = update.message.text.replace("/ah", "").replace("/ab", "").replace("/addhouse", "").replace("/addbiz", "").strip()
    lines = text.split("\n")
    out = []

    for line in lines:
        try:
            parts = line.split()

            if parts[0].startswith("/"):
                parts = parts[1:]

            st, obj_id, pay, ins, server = parts
            insured = ins.lower() == "yes"

            drop = calc_drop(st, int(pay), server, obj_type, insured)

            tax = get_tax(server, obj_type, insured)
            limit = HOUSE_LIMIT if obj_type == "house" else BIZ_LIMIT
            offset = SERVER_OFFSET.get(server, 0)

            rec = {
                "id": obj_id,
                "type": obj_type,
                "insured": insured,
                "server": server,
                "drop": drop,
                "start": parse_start(st),
                "base_tax": limit - ((int(pay) - offset) * tax)
            }

            records.append(rec)
            schedule(context.application, update.effective_chat.id, rec)

            out.append(f"✅ {obj_id} → {drop.strftime('%d.%m %H:%M')}")

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
        tax_now, limit = current_tax(rec)

        emoji = "🏠" if rec["type"] == "house" else "🏢"
        shield = "🛡" if rec["insured"] else "❌"

        msg += (
            f"{emoji} {rec['id']} | {SERVERS[rec['server']]}\n"
            f"📊 Налог: {tax_now:,} / {limit:,}\n"
            f"🚨 Слёт: {rec['drop'].strftime('%d.%m %H:%M')}\n"
            f"{shield} {'Страховка' if rec['insured'] else 'Без страховки'}\n\n"
        )

    await update.message.reply_text(msg)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler(["start"], start))
    app.add_handler(CommandHandler(["addhouse", "ah"], add_house))
    app.add_handler(CommandHandler(["addbiz", "ab"], add_biz))
    app.add_handler(CommandHandler(["list"], list_records))
    app.add_handler(CommandHandler(["del"], delete_record))
    app.add_handler(CommandHandler(["gone"], gone))

    app.run_polling()


if __name__ == "__main__":
    main()
