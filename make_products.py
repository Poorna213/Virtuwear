import json
import os
from PIL import Image

# 🗂️ Folder containing your outfit images
folder = r"C:\Users\Poorna\Desktop\VirtuWear_Project\assets\img_out"

# Supported file extensions
valid_exts = {".png", ".jpg", ".jpeg", ".webp"}

items = []
valid_files = []

# 🔍 Step 1: Scan and verify all valid images
for file in sorted(os.listdir(folder)):
    ext = os.path.splitext(file)[1].lower()
    if ext not in valid_exts:
        continue

    file_path = os.path.join(folder, file)
    try:
        # Try to open and verify the image (detects corrupted or incomplete files)
        with Image.open(file_path) as img:
            img.verify()
        valid_files.append(file)
    except Exception as e:
        print(f"⚠️ Skipping corrupted image: {file} ({e})")

# 🧠 Step 2: Build the JSON structure
for i, file in enumerate(valid_files):
    item = {
        "id": f"item{i+1}",
        "name": f"Style {os.path.splitext(file)[0]}",
        "thumb": f"assets/img_out/{file}",
        "src": f"assets/img_out/{file}",
        "position": {"x": 0, "y": -0.07, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 0.6, "y": 0.22, "z": 1}
    }
    items.append(item)

# 📦 Step 3: Save products.json next to assets folder
output_file = os.path.join(os.path.dirname(folder), "products.json")
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(items, f, indent=2)

# ✅ Step 4: Summary
print(f"\n✅ Generated {output_file}")
print(f"🖼️ Total valid images: {len(valid_files)}")
print(f"🚫 Skipped invalid/corrupted: {len(os.listdir(folder)) - len(valid_files)}")
