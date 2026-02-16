import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    Application,
)

from flask import Flask, request, Response
import asyncio

# ────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────
TELEGRAM_TOKEN = "8473065940:AAEBfJD0THr7pHx93SqBrdgc2qbNfU8_lYs"
TEMPLATE_PATH = "certificate_template.png"
FONT_PATH = "NotoKufiArabic-Bold.ttf"

POSITIONS = {"h1": (651, 470), "name": (650, 545), "role": (652, 615), "body": 665}
X_LEFT, X_RIGHT = 28, 1241
CHOICE, NAME, ROLE, BODY = range(4)
WEBHOOK_PATH = f"/{TELEGRAM_TOKEN}"

# ────────────────────────────────────────────────
# Arabic + Drawing (with debug prints)
# ────────────────────────────────────────────────
def convert_arabic(text: str) -> str:
    reshaped = arabic_reshaper.reshape(text)
    visual = get_display(reshaped)
    print(f"[TEXT DEBUG] Input: {text[:50]}...")
    print(f"[TEXT DEBUG] Reshaped: {reshaped[:50]}...")
    print(f"[TEXT DEBUG] Final visual (bidi): {visual[:50]}...")
    return visual

def draw_centered(draw, x, y, text, font, fill="black", already_visual=False):
    if already_visual:
        visual_text = text
    else:
        visual_text = convert_arabic(text)
    draw.text((x, y), visual_text, font=font, fill=fill, anchor="mm")

def wrap_text(draw, text, font, max_width):
    print("[WRAP DEBUG] Starting wrap for body")
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test_line = f"{current} {word}".strip() if current else word
        reshaped_test = arabic_reshaper.reshape(test_line)
        bbox = draw.textbbox((0, 0), reshaped_test, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = test_line
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    print(f"[WRAP DEBUG] Wrapped into {len(lines)} lines:")
    for i, ln in enumerate(lines, 1):
        print(f"  Line {i}: {ln}")
    return lines

def generate_certificate(choice_word, name, role, star_text):
    print("[CERT DEBUG] Starting certificate generation")
    img = Image.open(TEMPLATE_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype(FONT_PATH, 40)
        font_role = ImageFont.truetype(FONT_PATH, 30)
        print("[CERT DEBUG] Fonts loaded OK")
    except Exception as e:
        print(f"[CERT DEBUG] Font error: {e}")
        font_big = font_role = ImageFont.load_default()

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

    logical_lines = wrap_text(draw, body, font_big, max_width)

    sample_bbox = draw.textbbox((0, 0), convert_arabic("أ"), font=font_big)
    line_height = sample_bbox[3] - sample_bbox[1]

    for i, logical_line in enumerate(logical_lines, 1):
        reshaped = arabic_reshaper.reshape(logical_line)
        visual_line = get_display(reshaped)
        print(f"[CERT DEBUG] Drawing line {i}: {visual_line}")
        draw_centered(draw, center_x, y, visual_line, font_big, already_visual=True)
        y += line_height + 20

    bio = BytesIO()
    bio.name = "certificate.png"
    img.save(bio, "PNG")
    bio.seek(0)
    print("[CERT DEBUG] Certificate ready")
    return bio

# ────────────────────────────────────────────────
# Handlers (with anti-repeat fix)
# ────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("وفاة", callback_data="وفاة"),
                 InlineKeyboardButton("استشهاد", callback_data="استشهاد")]]
    await update.message.reply_text("اختر نوع الخبر:", reply_markup=InlineKeyboardMarkup(keyboard))
    return CHOICE

async def choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    print(f"[HANDLER DEBUG] Choice: {query.data}")
    await query.answer()
    context.user_data["choice"] = query.data
    await query.edit_message_text(text="أدخل الاسم الكامل:", reply_markup=None)
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
# Flask + Webhook
# ────────────────────────────────────────────────
flask_app = Flask(__name__)
application: Application = None

@flask_app.route('/', methods=['GET'])
def hello():
    return "Bot is alive"

@flask_app.route(WEBHOOK_PATH, methods=['POST'])
async def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_data = request.get_json(silent=True)
        if json_data:
            update = Update.de_json(json_data, application.bot)
            if update:
                print(f"[WEBHOOK DEBUG] Received update: {update.to_dict()}")
                await application.process_update(update)
        return Response(status=200)
    return Response(status=403)

# ────────────────────────────────────────────────
# Startup
# ────────────────────────────────────────────────
async def startup():
    global application

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
        per_message=True,
    )
    application.add_handler(conv)

    print("[STARTUP] Initializing application...")
    await application.initialize()
    print("[STARTUP] Initialized OK")

    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not host:
        print("[STARTUP] Warning: No RENDER_EXTERNAL_HOSTNAME → local fallback")
        host = "127.0.0.1"
    webhook_url = f"https://{host}{WEBHOOK_PATH}"
    print(f"[STARTUP] Setting webhook: {webhook_url}")
    await application.bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    print("[STARTUP] Webhook set OK")

async def main():
    await startup()

    port = int(os.environ.get("PORT", 5000))
    print(f"[STARTUP] Running Flask on port {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    # Cleanup (rarely reached)
    print("[SHUTDOWN] Cleaning up...")
    await application.stop()
    await application.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
