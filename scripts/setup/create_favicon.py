"""Generate favicon from logo."""
from PIL import Image
import os

# Load the logo
logo_path = os.path.join('src', 'intellibox', 'web', 'static', 'logo.png')
logo = Image.open(logo_path)

# Create 32x32 favicon (standard size)
favicon_32 = logo.resize((32, 32), Image.Resampling.LANCZOS)
favicon_path = os.path.join('src', 'intellibox', 'web', 'static', 'favicon.ico')
favicon_32.save(favicon_path, format='ICO', sizes=[(32, 32)])

print(f"Favicon saved to {favicon_path}")

# Also create 16x16 for compatibility
favicon_16 = logo.resize((16, 16), Image.Resampling.LANCZOS)
favicon_multi_path = os.path.join('src', 'intellibox', 'web', 'static', 'favicon_multi.ico')
favicon_16.save(favicon_multi_path, format='ICO', sizes=[(16, 16), (32, 32)])

print(f"Multi-size favicon saved to {favicon_multi_path}")
