import os
import asyncio
from typing import Dict

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

DURATIONS = {
    "4h": 4 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "24h": 24 * 60 * 60,
}

# chat_id -> duration
active_cycles: Dict[int, int] = {}


async def is_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> bool:
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    if chat.type not in ("group", "supergroup"):
        return False

    try:
        member = await context.bot.get_chat_member(
            chat_id=chat.id,
            user_id=user.id
        )

        return member.status in ("administrator", "creator")

    except Exception:
        return False


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await is_admin(update, context):
        return

    await update.effective_message.reply_text(
        "Pin Cycle Bot\n\n"
        "Commands:\n"
        "/pin 4h\n"
        "/pin 8h\n"
        "/pin 12h\n"
        "/pin 24h"
    )


async def pin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not await is_admin(update, context):
        return

    message = update.effective_message
    chat = update.effective_chat

    if not message or not chat:
        return

    # Delete the admin's command immediately
    try:
        await message.delete()
    except Exception:
        pass

    # Check command
    if len(context.args) != 1:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "❌ Invalid command.\n\n"
                "Use:\n"
                "/pin 4h\n"
                "/pin 8h\n"
                "/pin 12h\n"
                "/pin 24h"
            )
        )
        return

    duration_text = context.args[0].lower()

    if duration_text not in DURATIONS:
        await context.bot.send_message(
            chat_id=chat.id,
            text=(
                "❌ Invalid duration.\n\n"
                "Only these are allowed:\n"
                "/pin 4h\n"
                "/pin 8h\n"
                "/pin 12h\n"
                "/pin 24h"
            )
        )
        return

    duration_seconds = DURATIONS[duration_text]
    hours = duration_text[:-1]

    # Start/restart the cycle
    active_cycles[chat.id] = duration_seconds

    # Alert
    await context.bot.send_message(
        chat_id=chat.id,
        text=(
            "✅ Pin Cycle is ready. Next post will be pinned for "
            f"{hours} hours, except admins."
        )
    )


async def handle_member_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or not user:
        return

    if chat.type not in ("group", "supergroup"):
        return

    # Ignore bots
    if user.is_bot:
        return

    # No active cycle
    if chat.id not in active_cycles:
        return

    # Check whether sender is an admin
    try:
        member = await context.bot.get_chat_member(
            chat_id=chat.id,
            user_id=user.id
        )

        # Admins and creator are ignored
        if member.status in ("administrator", "creator"):
            return

    except Exception:
        return

    # Get selected duration
    duration_seconds = active_cycles.pop(chat.id)

    # Pin the member's message
    try:
        await context.bot.pin_chat_message(
            chat_id=chat.id,
            message_id=message.message_id,
            disable_notification=False
        )
    except Exception as error:
        print(f"Pin error: {error}")
        return

    # Start unpin timer
    asyncio.create_task(
        unpin_after_time(
            context,
            chat.id,
            message.message_id,
            duration_seconds
        )
    )


async def unpin_after_time(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    duration_seconds: int
):
    try:
        await asyncio.sleep(duration_seconds)

        await context.bot.unpin_chat_message(
            chat_id=chat_id,
            message_id=message_id
        )

    except asyncio.CancelledError:
        pass

    except Exception as error:
        print(f"Unpin error: {error}")


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):
    print(f"Bot error: {context.error}")


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it to Railway Variables."
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("pin", pin_command)
    )

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            handle_member_message
        )
    )

    app.add_error_handler(error_handler)

    print("PinCycleBOT is running...")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
