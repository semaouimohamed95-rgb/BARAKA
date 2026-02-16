import os
from io import BytesIO
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

# ----------------------
# Config
# ----------------------
TELEGRAM_TOKEN = "8473065940:AAEBfJD0THr7pHx93SqBrdgc2qbNfU8_lYs"  # Set this in your environment
TEMPLATE_PATH = "certificate_template.png"
FONT_PATH = "NotoKufiArabic-Bold.ttf"

POSITIONS = {
    "h1": (651, 470),
    "name": (650, 545),
    "role": (652, 615),
    "body": 665
}

X_LEFT, X_RIGHT = 28, 1241
CHOICE, NAME, ROLE, BODY = range(4)

# ----------------------
# Arabic convert
# ----------------------
def convert_arabic(text: str) -> str:
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

# ----------------------
# Drawing
# ----------------------
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

    draw_centered(draw, *POSITIONS["h1"], h1, font_big)
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

# ----------------------
# Handlers
# ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("وفاة", callback_data="وفاة"),
         InlineKeyboardButton("استشهاد", callback_data="استشهاد")]
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
    await update.message.reply_text("أدخل النص الذي مكان النجوم (مثال: لعائلة فلان الكريمة):")
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

# ────────────────────────────────────────────────
#   SEPARATE FLASK HELLO WORLD (completely independent)
# ────────────────────────────────────────────────

from flask import Flask

flask_app = Flask(__name__)

@flask_app.route('/')
def hello():
    return """
    <h1 style="text-align: center; margin-top: 100px; font-family: Arial, sans-serif;">
        مرحباً بالعالم 🌍<br>
        <small>Hello World from Flask!</small>
    </h1>
    """

# ────────────────────────────────────────────────
#   Main
# ────────────────────────────────────────────────

if __name__ == "__main__":
    import threading

    # Create the PTB Application once (outside threads)
    print("Building Telegram application...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

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

    app.add_handler(conv)

    # Function to run the bot (blocking)
    def run_telegram_bot():
        print("Telegram bot is starting (polling)...")
        # You can add drop_pending_updates=True if you want
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,   # ← change if needed
            # stop_signals=None           # ← optional: disables signal handling (try if still issues)
        )

    # Start Flask web server in background thread
    def run_flask():
        print("Starting Flask server on http://0.0.0.0:5000 ...")
        # Important: use 0.0.0.0 so Render can see it
        flask_app.run(
            host="0.0.0.0",
            port=5000,
            debug=False,           # ← turn off debug in production
            use_reloader=False     # ← important in threaded setup
        )

    # Start Flask in a daemon thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run Telegram bot in **main thread** (blocking call)
    run_telegram_bot()
