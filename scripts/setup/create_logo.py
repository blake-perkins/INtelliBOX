"""Generate INtelliBOX logo as PNG."""
from PIL import Image, ImageDraw, ImageFont
import os

# Create a new image with transparency (wider to include icon)
width = 350
height = 60
img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Colors
cyan = (0, 168, 232)  # #00a8e8
white = (255, 255, 255)
dark_bg = (44, 62, 80)  # #2c3e50 for background reference

# Draw mail icon
icon_x = 5
icon_y = 5
icon_size = 50
icon_radius = 8

# Blue rounded rectangle for mail box
draw.rounded_rectangle(
    [(icon_x, icon_y), (icon_x + icon_size, icon_y + icon_size)],
    radius=icon_radius,
    fill=cyan
)

# White envelope inside
envelope_padding = 8
env_x1 = icon_x + envelope_padding
env_y1 = icon_y + envelope_padding + 5
env_x2 = icon_x + icon_size - envelope_padding
env_y2 = icon_y + icon_size - envelope_padding - 5
envelope_radius = 4

# Envelope rectangle
draw.rounded_rectangle(
    [(env_x1, env_y1), (env_x2, env_y2)],
    radius=envelope_radius,
    fill=white
)

# Envelope flap (V shape)
env_center_x = (env_x1 + env_x2) / 2
env_center_y = (env_y1 + env_y2) / 2
draw.line(
    [(env_x1, env_y1), (env_center_x, env_center_y)],
    fill=cyan,
    width=3
)
draw.line(
    [(env_center_x, env_center_y), (env_x2, env_y1)],
    fill=cyan,
    width=3
)

# Connection dots and lines
dot_x = icon_x + icon_size + 5
dot_radius = 4
dot_spacing = 12

for i in range(3):
    dot_y = icon_y + 12 + (i * dot_spacing)
    # Line from box to dot
    draw.line(
        [(icon_x + icon_size, dot_y), (dot_x, dot_y)],
        fill=cyan,
        width=2
    )
    # Dot
    draw.ellipse(
        [(dot_x - dot_radius, dot_y - dot_radius),
         (dot_x + dot_radius, dot_y + dot_radius)],
        fill=cyan
    )

# Try to use a nice font, fallback to default
try:
    font = ImageFont.truetype("arialbd.ttf", 42)
except:
    try:
        font = ImageFont.truetype("arial.ttf", 42)
    except:
        font = ImageFont.load_default()

# Draw the text
text_x = dot_x + dot_radius + 10
text_y = 8

# Draw "IN" in cyan
text = "IN"
draw.text((text_x, text_y), text, font=font, fill=cyan)
bbox = draw.textbbox((text_x, text_y), text, font=font)
text_x = bbox[2]

# Draw "telli" in white
text = "telli"
draw.text((text_x, text_y), text, font=font, fill=white)
bbox = draw.textbbox((text_x, text_y), text, font=font)
text_x = bbox[2]

# Draw "BOX" in cyan
text = "BOX"
draw.text((text_x, text_y), text, font=font, fill=cyan)

# Save the image
output_path = os.path.join('src', 'intellibox', 'web', 'static', 'logo.png')
img.save(output_path, 'PNG')
print(f"Logo saved to {output_path}")
print(f"Image size: {img.size}")
