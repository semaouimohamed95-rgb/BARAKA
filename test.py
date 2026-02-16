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
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
PORT = int(os.environ.get("PORT", 10000))
RENDER_NAME = os.environ.get("RENDER_SERVICE_NAME")
WEBHOOK_URL = f"https://{RENDER_NAME}/{TELEGRAM_TOKEN}"

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
# Arabic convert (Fixed)
# ----------------------
def convert_arabic(text: str) -> str:
    # Reshape handles the letter connections (e.g., عـبـار)
    reshaped = arabic_reshaper.reshape(text)
    # get_display handles the Right-to-Left direction
    return get_display(reshaped)

# ----------------------
# Drawing
# ----------------------
def draw_centered(draw, x, y, logical_text, font, fill="black"):
    visual_text = convert_arabic(logical_text)
    # Use anchor="mm" for true middle-middle alignment in modern Pillow
    # This prevents manual bbox calculation errors
    draw.text((x, y), visual_text, font=font, fill=fill, anchor="mm")

def wrap_text(draw, text, font, max_width):
    """Wrap using logical Arabic, convert only for measuring."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        # Check if current line + next word fits
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

    # H1 constant
    h1 = f"ببالغ الحزن والأسى وبقلوب راضية بقضاء الله وقدره تلقينا نبأ {choice_word}"

    # Body constant
    body = (
        "وعلى إثر هذا المصاب الجلل يتقدم الأستاذ عبار صلاح الدين "
        "وبالنيابة عن المكتب الولائي سيدي بلعباس بأصدق التعازي والمواساة "
        f"{star_text} "
        "ولكل عائلة المتوفى سائلا المولى أن يتقبله ويتغمده برحمته الواسعة "
        "ويسكنه الفردوس الأعلى ويلهم ذويه الصبر والسلوان."
    )

    # Draw everything
    draw_centered(draw, *POSITIONS["h1"], h1, font_big)
    draw_centered(draw, *POSITIONS["name"], name, font_big, "white")
    draw_centered(draw, *POSITIONS["role"], role, font_role, "green")

    y = POSITIONS["body"]
    center_x = (X_LEFT + X_RIGHT) // 2
    max_width = X_RIGHT - X_LEFT

    lines = wrap_text(draw, body, font_big, max_width)
    
    # Calculate line height using a standard character
    sample_bbox = draw.textbbox((0, 0), convert_arabic("أ"), font=font_big)
    line_height = sample_bbox[3] - sample_bbox[1]

    for line in lines:
        draw_centered(draw, center_x, y, line, font_big)
        y += line_height + 20 # Increased spacing for Kufi font readability

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
    await update.message.reply_text(
        "أدخل النص الذي مكان النجوم (مثال: لعائلة فلان الكريمة):"
    )
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

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":
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

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=WEBHOOK_URL,
    )

