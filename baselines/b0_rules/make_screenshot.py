from PIL import Image, ImageDraw, ImageFont

with open("run_output.txt", encoding="utf-8") as f:
    lines = [f"$ python run_baseline.py --input examples/test1.txt"] + f.read().splitlines()

font = ImageFont.truetype(
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 15
)
line_h = 20
pad = 24
width = 980
height = pad * 2 + line_h * len(lines) + 40

img = Image.new("RGB", (width, height), (30, 30, 30))
draw = ImageDraw.Draw(img)

# fake title bar
draw.rectangle([0, 0, width, 34], fill=(45, 45, 45))
for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    draw.ellipse([16 + i * 22, 11, 16 + i * 22 + 12, 23], fill=c)

y = 34 + 16
for line in lines:
    color = (150, 255, 150) if line.startswith("$") else (220, 220, 220)
    draw.text((pad, y), line, font=font, fill=color)
    y += line_h

img.save("baseline_run_screenshot.png")
print("saved baseline_run_screenshot.png", img.size)
