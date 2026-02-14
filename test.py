from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

# ----------------------
# User content
# ----------------------
name_text = "الدبـــار عبد الناصر"
h1_text = "إستشهاد إبن الله"
role_text = "عضو الجمعية الخيرية"
body_text = ("وعلى إثر هذا المصاب الجلل يتقدم الأستاذ عبار صلاح الدين وبالنيابة عن المكتب "
             "الولائي سيدي بلعباس بأصدق التعازي والمواساة لعائلة الشـ.ـهـ.ـداء ولمكتب جمعية "
             "البركة الجزائرية في قطاع  غـ.ـزة سائلا المولى أن يتقبل شـ.ـهـ.ـدائهم ويتغمدهم "
             "برحمته الواسعة ويسكنهم الفردوس الأعلى ويلهم ذويهم الصبر والسلوان.")

# ----------------------
# Certificate template
# ----------------------
image_path = "certificate_template.png"
output_path = "certificate_final.png"

# ----------------------
# Font setup
# ----------------------
font_name_h1 = ImageFont.truetype("NotoKufiArabic-Bold.ttf", 40)
font_name_name = ImageFont.truetype("NotoKufiArabic-Bold.ttf", 40)
font_name_role = ImageFont.truetype("NotoKufiArabic-Bold.ttf", 30)
font_name_body = ImageFont.truetype("NotoKufiArabic-Bold.ttf", 40)

# ----------------------
# Positions (center of text)
# ----------------------
positions = {
    "h1": (651, 470),
    "name": (650, 545),
    "role": (652, 615),
    "body": 665  # starting y-coordinate for body
}
x_left, x_right = 28, 1241  # body text limits

# ----------------------
# Load image
# ----------------------
img = Image.open(image_path).convert("RGB")
draw = ImageDraw.Draw(img)

# ----------------------
# Helper for Arabic centered text
# ----------------------
def draw_centered_text(draw, x_center, y, text, font, fill="black"):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    bbox = draw.textbbox((0,0), bidi_text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text((x_center - w // 2, y - h // 2), bidi_text, font=font, fill=fill)
    return h  # return height for spacing

# ----------------------
# Draw h1, name, role
# ----------------------
draw_centered_text(draw, positions["h1"][0], positions["h1"][1], h1_text, font_name_h1, "black")
draw_centered_text(draw, positions["name"][0], positions["name"][1], name_text, font_name_name, "white")
draw_centered_text(draw, positions["role"][0], positions["role"][1], role_text, font_name_role, "green")

# ----------------------
# Draw body with word-wrapping and pixel width limits
# ----------------------
y_body = positions["body"]
x_center_body = (x_left + x_right) // 2

words = body_text.split()
lines = []
current_line = ""

for word in words:
    test_line = f"{current_line} {word}".strip()
    reshaped_test_line = get_display(arabic_reshaper.reshape(test_line))
    bbox = draw.textbbox((0,0), reshaped_test_line, font=font_name_body)
    w = bbox[2] - bbox[0]
    if w <= (x_right - x_left):
        current_line = test_line
    else:
        lines.append(current_line)
        current_line = word
if current_line:
    lines.append(current_line)

# Draw each line with tight spacing
sample_h = draw.textbbox((0,0), get_display(arabic_reshaper.reshape("أ")), font=font_name_body)[3]
for line in lines:
    draw_centered_text(draw, x_center_body, y_body, line, font_name_body, "black")
    y_body += sample_h + 2  # spacing between lines

# ----------------------
# Save final image
# ----------------------
img.save(output_path)
print(f"Certificate generated: {output_path}")
