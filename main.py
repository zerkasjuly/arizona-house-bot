import os
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
MSK = timezone(timedelta(hours=3))

records = []
jobs = {}

SERVERS = {
    "01": "Phoenix",
    "02": "Tucson",
    "03": "Scottdale",
    "04": "Chandler",
    "05": "Brainburg",
    "06": "SaintRose",
    "07": "Mesa",
    "08": "Red-Rock",
    "09": "Yuma",
    "10": "Surprise",
    "11": "Prescott",
    "12": "Glendale",
    "13": "Kingman",
    "14": "Winslow",
    "15": "Payson",
    "16": "Gilbert",
    "17": "Show-Low",
    "18": "Casa-Grande",
    "19": "Page",
    "20": "Sun-City",
    "21": "Queen-Creek",
    "22": "Sedona",
    "23": "Holiday",
    "24": "Wednesday",
    "25": "Yava",
    "26": "Faraway",
    "27": "Bumble-Bee",
    "28": "Mirage"
}


def now():
    return datetime.now(MSK)


def cancel_jobs(house):
    if house in jobs:
        for job in jobs[house]:
            job.schedule_removal()
        del jobs[house]


def calc_drop(start_time, payday, insured):
    current = datetime.strptime(start_time, "%H:%M").replace(
        year=now().year,
        month=now().month,
        day=now().day,
        tzinfo=MSK
    )

    if current > now():
        current -= timedelta(days=1)

    p = payday

    while True:
        current += timedelta(hours=1)
        p -= 1 if insured else 2

        if insured and p == 2:
            return current + timedelta(hours=1), current + timedelta(hours=2)

        if not insured and p <= 1:
            return current, None


async def notify(context):
    d = context.job.data

    if d["type"] == "possible":
        msg = f"⚠️ Возможно в этот пейдей слетит №{d['house']} на сервере {SERVERS[d['server']]}"
    elif d["type"] == "final":
        msg = f"🚨 В этот пейдей слетит №{d['house']} на сервере {SERVERS[d['server']]}"
    else:
        msg = f"🚨 Дом №{d['house']} на сервере {SERVERS[d['server']]} слетает через {d['mins']} минут"

    await context.bot.send_message(context.job.chat_id, msg)


async def cleanup(context):
    house = context.job.data
    global records

    records = [r for r in records if r["house"] != house]
    cancel_jobs(house)


def schedule(app, chat_id, house, server, insured, drop, alt):
    cancel_jobs(house)
    jobs[house] = []

    if insured:
        for dt, t in [(drop, "possible"), (alt, "final")]:
            sec = (dt - now()).total_seconds() - 60
            if sec > 0:
                job = app.job_queue.run_once(
                    notify,
                    when=sec,
                    chat_id=chat_id,
                    data={
                        "house": house,
                        "server": server,
                        "type": t
                    }
                )
                jobs[house].append(job)

        sec = (alt - now()).total_seconds()
        if sec > 0:
            job = app.job_queue.run_once(cleanup, when=sec, data=house)
            jobs[house].append(job)

    else:
        for mins in [10, 5]:
            sec = (drop - now()).total_seconds() - mins * 60
            if sec > 0:
                job = app.job_queue.run_once(
                    notify,
                    when=sec,
                    chat_id=chat_id,
                    data={
                        "house": house,
                        "server": server,
                        "mins": mins,
                        "type": "normal"
                    }
                )
                jobs[house].append(job)

        sec = (drop - now()).total_seconds()
        if sec > 0:
            job = app.job_queue.run_once(cleanup, when=sec, data=house)
            jobs[house].append(job)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/add\n/list\n/edit\n/del\n/gone"
    )


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("/add", "").strip()
    lines = text.split("\n")

    out = []

    for line in lines:
        try:
            st, house, pay, ins, server = line.split()

            insured = ins.lower() == "yes"
            drop, alt = calc_drop(st, int(pay), insured)

            records.append({
                "house": house,
                "insured": insured,
                "server": server,
                "drop": drop,
                "alt": alt
            })

            schedule(
                context.application,
                update.effective_chat.id,
                house,
                server,
                insured,
                drop,
                alt
            )

            extra = f" / {alt.strftime('%H:%M')}?" if alt else ""
            out.append(f"✅ {house} → {drop.strftime('%d.%m %H:%M')}{extra}")

        except:
            out.append(f"❌ Ошибка: {line}")

    await update.message.reply_text("\n".join(out))


async def delete_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    house = context.args[0]
    global records

    records = [r for r in records if r["house"] != house]
    cancel_jobs(house)

    await update.message.reply_text(f"🗑 Удалён {house}")


async def gone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    house = context.args[0]
    global records

    records = [r for r in records if r["house"] != house]
    cancel_jobs(house)

    await update.message.reply_text(f"✅ Подтверждён слёт {house}")


async def edit_record(update: Update, context: ContextTypes.DEFAULT_TYPE):
    house, st, pay, ins, server = context.args
    insured = ins.lower() == "yes"

    for i, r in enumerate(records):
        if r["house"] == house:
            drop, alt = calc_drop(st, int(pay), insured)

            records[i] = {
                "house": house,
                "insured": insured,
                "server": server,
                "drop": drop,
                "alt": alt
            }

            schedule(
                context.application,
                update.effective_chat.id,
                house,
                server,
                insured,
                drop,
                alt
            )

            await update.message.reply_text(f"✏️ Обновлён {house}")
            return

    await update.message.reply_text("Дом не найден")


async def list_records(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global records
    records = [r for r in records if (r["alt"] or r["drop"]) > now()]

    if not records:
        await update.message.reply_text("Список пуст")
        return

    grouped = {}

    for r in sorted(records, key=lambda x: x["drop"]):
        grouped.setdefault(r["server"], []).append(r)

    msg = "🔥 Список слётов\n\n"

    for server, houses in grouped.items():
        msg += f"🌍 {SERVERS[server]} ({server})\n"
        
for r in houses:
    if r["alt"]:
        msg += (
            f"🏠 {r['house']}\n"
            f"⏰ Возможно: {r['drop'].strftime('%d.%m %H:%M')}\n"
            f"🚨 Точно: {r['alt'].strftime('%d.%m %H:%M')}\n"
            f"🛡 Страховка\n\n"
        )
    else:
        msg += (
            f"🏠 {r['house']}\n"
            f"🚨 Слёт: {r['drop'].strftime('%d.%m %H:%M')}\n"
            f"🛡 Без страховки\n\n"
        )

    await update.message.reply_text(msg)


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("list", list_records))
    app.add_handler(CommandHandler("edit", edit_record))
    app.add_handler(CommandHandler("delete", delete_record))
    app.add_handler(CommandHandler("del", delete_record))
    app.add_handler(CommandHandler("gone", gone))

    app.run_polling()


if __name__ == "__main__":
    main()
