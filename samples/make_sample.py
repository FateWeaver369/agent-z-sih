"""
Generates a synthetic 'webpage screenshot' for testing the perception
pipeline without needing a real browser capture yet.

Run: python samples/make_sample.py
"""
from PIL import Image, ImageDraw, ImageFont

W, H = 800, 500
img = Image.new("RGB", (W, H), "white")
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
except Exception:
    font = font_small = font_title = ImageFont.load_default()

# Header bar
draw.rectangle([0, 0, W, 60], fill=(30, 41, 59))
draw.text((20, 18), "AgentZ Demo Page", font=font_title, fill="white")

# Nav links
draw.text((600, 20), "Home", font=font_small, fill="white")
draw.text((670, 20), "About", font=font_small, fill="white")
draw.text((740, 20), "Login", font=font_small, fill="white")

# Search input box
draw.rectangle([60, 100, 400, 140], outline=(100, 100, 100), width=2, fill=(245, 245, 245))
draw.text((75, 110), "Search", font=font, fill=(120, 120, 120))

# GO button
draw.rectangle([420, 100, 500, 140], fill=(37, 99, 235))
draw.text((445, 110), "GO", font=font, fill="white")

# Card / content block with a secondary button
draw.rectangle([60, 200, 500, 340], outline=(200, 200, 200), width=2)
draw.text((80, 220), "Welcome back!", font=font, fill=(20, 20, 20))
draw.text((80, 255), "Enter your details below to continue.", font=font_small, fill=(80, 80, 80))

draw.rectangle([80, 290, 220, 325], fill=(16, 185, 129))
draw.text((105, 298), "Sign Up", font=font, fill="white")

draw.rectangle([240, 290, 380, 325], outline=(16, 185, 129), width=2)
draw.text((260, 298), "Cancel", font=font, fill=(16, 185, 129))

img.save("samples/sample_page.png")
print("Saved samples/sample_page.png")
