import os
import asyncio
import threading
from io import BytesIO
from flask import Flask, request
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
# CONFIG
# =====================================================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "certificate_template.png")
FONT_PATH = os.path.join(BASE_DIR, "NotoKufiArabic-Bold.ttf")

POSITIONS = {
    "h1": (651, 470),
    "name": (650, 580),
    "role": (652, 640),
    "body": 665
}

X_LEFT, X_RIGHT = 28, 1241
CHOICE, NAME, ROLE, BODY = range(4)

# =====================================================
# FLASK
# =====================================================

appd = Flask(__name__)

@appd.route("/")
def home():
    return "Bot is alive", 200


# =====================================================
# ARABIC PROCESSING
# =====================================================

def convert_arabic(text: str) -> str:
    return text


# =====================================================
# IMAGE GENERATION
# =====================================================

def draw_centered(draw, x, y, logical_text, font, fill="black"):
    visual_text = convert_arabic(logical_text)
    draw.text((x, y), visual_text, font=font, fill=fill, anchor="mm")


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test_line = f"{current} {word}".strip()
        visual = convert_arabic(test_line)
        bbox = draw.textbbox((0, 0), visual, font=font)
        width = bbox[2] - bbox[0]

        if width <= max_width:
            current = test_line
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def generate_certificate(choice_word, name, role, star_text):
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_big = ImageFont.truetype(FONT_PATH, 40)
    font_role = ImageFont.truetype(FONT_PATH, 30)

    h1 = f"ببالغ الحزن والأسى وبقلوب راضية بقضاء الله وقدره تلقينا نبأ {choice_word}"

    body = (
        "وعلى إثر هذا المصاب الجلل يتقدم الأستاذ عبار صلاح الدين "
        "وبالنيابة عن المكتب الولائي سيدي بلعباس بأصدق التعازي والمواساة "
        f"{star_text} "
        "ولكل عائلة المتوفى سائلا المولى أن يتقبله ويتغمده برحمته الواسعة "
        "ويسكنه الفردوس الأعلى ويلهم ذويه الصبر والسلوان."
    )

    draw_centered(draw, *POSITIONS["h1"], h1,  ImageFont.truetype(FONT_PATH, 30))
    draw_centered(draw, *POSITIONS["name"], name, font_big, "white")
    draw_centered(draw, *POSITIONS["role"], role, font_role, "green")

    y = POSITIONS["body"]
    center_x = (X_LEFT + X_RIGHT) // 2
    max_width = X_RIGHT - X_LEFT

    lines = wrap_text(draw, body, font_big, max_width)
    sample_bbox = draw.textbbox((0, 0), convert_arabic("أ"), font=font_big)
    line_height = sample_bbox[3] - sample_bbox[1]

    for line in lines:
        draw_centered(draw, center_x, y, line, font_big)
        y += line_height + 20

    bio = BytesIO()
    bio.name = "certificate.png"
    img.save(bio, "PNG")
    bio.seek(0)

    return bio


# =====================================================
# TELEGRAM HANDLERS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("وفاة", callback_data="وفاة"),
            InlineKeyboardButton("استشهاد", callback_data="استشهاد")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر نوع الخبر:", reply_markup=reply_markup)
    return CHOICE


async def choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["choice"] = query.data
    await query.edit_message_text("أدخل الاسم الكامل:")
    return NAME


async def name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("أدخل الصفة:")
    return ROLE


async def role_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["role"] = update.message.text
    await update.message.reply_text("أدخل النص الذي مكان النجوم:")
    return BODY


async def body_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stars"] = update.message.text

    bio = generate_certificate(
        context.user_data["choice"],
        context.user_data["name"],
        context.user_data["role"],
        context.user_data["stars"]
    )

    await update.message.reply_photo(photo=bio, caption="تم إنشاء الشهادة ✅")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("تم الإلغاء.")
    return ConversationHandler.END


# =====================================================
# TELEGRAM APPLICATION SETUP
# =====================================================

loop = asyncio.new_event_loop()

def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CHOICE: [CallbackQueryHandler(choice_handler)],
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_input)],
        ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, role_input)],
        BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_input)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

application.add_handler(conv)

async def init_bot():
    await application.initialize()
    await application.start()

asyncio.run_coroutine_threadsafe(init_bot(), loop)


# =====================================================
# WEBHOOK
# =====================================================

@appd.route(f"/webhook/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)

    asyncio.run_coroutine_threadsafe(
        application.process_update(update),
        loop
    )

    return "OK", 200


# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":
    appd.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))



