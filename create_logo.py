"""Generate INtelliBOX logo as PNG."""
from PIL import Image, ImageDraw, ImageFont
import os

# Create a new image with transparency
width = 280
height = 60
img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Colors
cyan = (0, 168, 232)  # #00a8e8
white = (255, 255, 255)
dark_bg = (44, 62, 80)  # #2c3e50 for background reference

# Try to use a nice font, fallback to default
try:
    # Try Arial Bold
    font = ImageFont.truetype("arial.ttf", 48)
except:
    try:
        font = ImageFont.truetype("arialbd.ttf", 48)
    except:
        # Fallback to default
        font = ImageFont.load_default()

# Draw the text as one piece with color spans
# Position text
x = 10
y = 5

# Draw "IN" in cyan
text = "IN"
draw.text((x, y), text, font=font, fill=cyan)
bbox = draw.textbbox((x, y), text, font=font)
x = bbox[2]

# Draw "telli" in white
text = "telli"
draw.text((x, y), text, font=font, fill=white)
bbox = draw.textbbox((x, y), text, font=font)
x = bbox[2]

# Draw "BOX" in cyan
text = "BOX"
draw.text((x, y), text, font=font, fill=cyan)

# Save the image
output_path = os.path.join('src', 'emailtools', 'web', 'static', 'logo.png')
img.save(output_path, 'PNG')
print(f"Logo saved to {output_path}")
print(f"Image size: {img.size}")
