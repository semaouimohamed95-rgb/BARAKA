import os
import asyncio
import threading
import logging
from io import BytesIO

from flask import Flask, request, jsonify
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# =====================================================
# CONFIGURATION
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", "10000"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "certificate_template.png")
FONT_PATH = os.path.join(BASE_DIR, "NotoKufiArabic-Bold.ttf")

POSITIONS = {
    "h1": (651, 470),
    "name": (650, 565),
    "role": (652, 625),
    "body": 665,
}

X_LEFT, X_RIGHT = 28, 1241

CHOICE, NAME, ROLE, BODY = range(4)

# =====================================================
# VALIDATION
# =====================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "TELEGRAM_TOKEN is missing from environment variables."
    )

if not WEBHOOK_URL.startswith("https://"):
    raise RuntimeError(
        "WEBHOOK_URL must be the public HTTPS URL of your Render service."
    )

for file_path in (TEMPLATE_PATH, FONT_PATH):
    if not os.path.isfile(file_path):
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

WEBHOOK_PATH = f"/webhook/{TELEGRAM_TOKEN}"
FULL_WEBHOOK_URL = f"{WEBHOOK_URL}{WEBHOOK_PATH}"

# =====================================================
# FLASK
# =====================================================

appd = Flask(__name__)

bot_ready = threading.Event()
bot_startup_error = None


@appd.route("/", methods=["GET"])
def home():
    if bot_ready.is_set():
        return jsonify({
            "status": "ok",
            "bot": "initialized",
        }), 200

    return jsonify({
        "status": "starting",
        "bot": "not_ready",
    }), 503


@appd.route("/health", methods=["GET"])
def health():
    return jsonify({
        "service": "running",
        "bot_ready": bot_ready.is_set(),
    }), 200


# =====================================================
# ARABIC TEXT PROCESSING
# =====================================================

def convert_arabic(text: str) -> str:
    """Connect letters (reshape) then reorder for visual RTL (bidi)."""
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(text))


# =====================================================
# IMAGE GENERATION
# =====================================================

def draw_centered(draw, x, y, logical_text, font, fill="black"):
    visual_text = convert_arabic(logical_text)

    draw.text(
        (x, y),
        visual_text,
        font=font,
        fill=fill,
        anchor="mm",
    )


def wrap_text(draw, text, font, max_width):
    """Wrap Arabic text based on its rendered width."""
    words = text.split()
    lines = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        visual = convert_arabic(candidate)

        bbox = draw.textbbox(
            (0, 0),
            visual,
            font=font,
        )
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)

            current = word

            if not lines and width > max_width:
                logger.warning(
                    "A word exceeds the configured text width."
                )

    if current:
        lines.append(current)

    return lines


def generate_certificate(choice_word, name, role, star_text):
    with Image.open(TEMPLATE_PATH) as template:
        img = template.convert("RGB")

    draw = ImageDraw.Draw(img)

    font_big = ImageFont.truetype(FONT_PATH, 40)
    font_heading = ImageFont.truetype(FONT_PATH, 35)
    font_role = ImageFont.truetype(FONT_PATH, 30)

    heading = (
        "ببالغ الحزن والأسى وبقلوب راضية بقضاء الله وقدره "
        f"تلقينا نبأ {choice_word}"
    )

    body = (
        "وعلى إثر هذا المصاب الجلل يتقدم الأستاذ عبار صلاح الدين "
        "وبالنيابة عن المكتب الولائي سيدي بلعباس بأصدق التعازي والمواساة "
        f"{star_text} "
        "ولكل عائلة المتوفى سائلا المولى أن يتقبله ويتغمده برحمته الواسعة "
        "ويسكنه الفردوس الأعلى ويلهم ذويه الصبر والسلوان."
    )

    draw_centered(
        draw,
        *POSITIONS["h1"],
        heading,
        font_heading,
    )

    draw_centered(
        draw,
        *POSITIONS["name"],
        name,
        font_big,
        "white",
    )

    draw_centered(
        draw,
        *POSITIONS["role"],
        role,
        font_role,
        "green",
    )

    center_x = (X_LEFT + X_RIGHT) // 2
    max_width = X_RIGHT - X_LEFT
    y = POSITIONS["body"]

    lines = wrap_text(draw, body, font_big, max_width)

    sample_bbox = draw.textbbox(
        (0, 0),
        convert_arabic("أ"),
        font=font_big,
    )

    line_height = sample_bbox[3] - sample_bbox[1]

    for line in lines:
        draw_centered(
            draw,
            center_x,
            y,
            line,
            font_big,
        )
        y += line_height + 20

    output = BytesIO()
    output.name = "certificate.png"

    img.save(output, format="PNG")
    img.close()

    output.seek(0)
    return output


# =====================================================
# TELEGRAM HANDLERS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton(
                "وفاة",
                callback_data="وفاة",
            ),
            InlineKeyboardButton(
                "استشهاد",
                callback_data="استشهاد",
            ),
        ]
    ]

    await update.effective_message.reply_text(
        "اختر نوع الخبر:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return CHOICE


async def choice_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    context.user_data["choice"] = query.data

    await query.edit_message_text("أدخل الاسم الكامل:")
    return NAME


async def name_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = (update.effective_message.text or "").strip()

    if not name:
        await update.effective_message.reply_text(
            "الرجاء إدخال الاسم الكامل."
        )
        return NAME

    context.user_data["name"] = name

    await update.effective_message.reply_text("أدخل الصفة:")
    return ROLE


async def role_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    role = (update.effective_message.text or "").strip()

    if not role:
        await update.effective_message.reply_text(
            "الرجاء إدخال الصفة."
        )
        return ROLE

    context.user_data["role"] = role

    await update.effective_message.reply_text(
        "أكمل بأصدق التعازي والمواساة لمن؟"
    )

    return BODY


async def body_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    star_text = (message.text or "").strip()

    if not star_text:
        await message.reply_text(
            "الرجاء إدخال النص المطلوب."
        )
        return BODY

    context.user_data["stars"] = star_text

    try:
        certificate = await asyncio.to_thread(
            generate_certificate,
            context.user_data["choice"],
            context.user_data["name"],
            context.user_data["role"],
            context.user_data["stars"],
        )

        try:
            await message.reply_photo(
                photo=certificate,
                caption="تم إنشاء الشهادة ✅",
            )
        finally:
            certificate.close()

    except Exception:
        logger.exception("Certificate generation or delivery failed.")

        await message.reply_text(
            "حدث خطأ أثناء إنشاء الشهادة أو إرسالها. "
            "حاول مرة أخرى لاحقًا."
        )

        return ConversationHandler.END

    return ConversationHandler.END


async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.effective_message.reply_text("تم الإلغاء.")
    return ConversationHandler.END


# =====================================================
# TELEGRAM APPLICATION
# =====================================================

application = (
    ApplicationBuilder()
    .token(TELEGRAM_TOKEN)
    .build()
)

conv = ConversationHandler(
    entry_points=[
        CommandHandler("start", start),
    ],
    states={
        CHOICE: [
            CallbackQueryHandler(
                choice_handler,
                pattern=r"^(وفاة|استشهاد)$",
            ),
        ],
        NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                name_input,
            ),
        ],
        ROLE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                role_input,
            ),
        ],
        BODY: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                body_input,
            ),
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
    ],
    per_message=False,
)

application.add_handler(conv)

# =====================================================
# ASYNCIO BACKGROUND THREAD
# =====================================================

loop = asyncio.new_event_loop()


async def init_bot():
    global bot_startup_error

    try:
        await application.initialize()

        await application.bot.set_webhook(
            url=FULL_WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES,
        )

        await application.start()

        bot_ready.set()

        logger.info(
            "Bot initialized. Webhook registered successfully."
        )

    except Exception as exc:
        bot_startup_error = str(exc)

        logger.exception("Bot initialization failed.")

        bot_ready.clear()


def run_event_loop():
    asyncio.set_event_loop(loop)

    try:
        loop.run_forever()
    finally:
        loop.close()


threading.Thread(
    target=run_event_loop,
    name="telegram-event-loop",
    daemon=True,
).start()

startup_future = asyncio.run_coroutine_threadsafe(
    init_bot(),
    loop,
)


# =====================================================
# WEBHOOK ENDPOINT
# =====================================================

@appd.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    if not bot_ready.is_set():
        return "Bot not ready", 503

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return "Invalid JSON", 400

    try:
        update = Update.de_json(data, application.bot)

        future = asyncio.run_coroutine_threadsafe(
            application.process_update(update),
            loop,
        )

        def report_processing_error(fut):
            try:
                fut.result()
            except Exception:
                logger.exception("Failed to process Telegram update.")

        future.add_done_callback(report_processing_error)

    except Exception:
        logger.exception("Failed to schedule Telegram update.")
        return "Internal server error", 500

    return "OK", 200


# =====================================================
# RUN LOCALLY
# =====================================================

if __name__ == "__main__":
    appd.run(
        host="0.0.0.0",
        port=PORT,
        debug=False,
        use_reloader=False,
    )
