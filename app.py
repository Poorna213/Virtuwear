"""
VirtuWear - Gemini image backend

- Serves index.html and assets
- GET  /api/outfits -> list files inside assets/img_out
- POST /api/tryon   -> takes:
      photo  (uploaded user image)
      outfit (filename from assets/img_out)
      prompt (optional text)
  -> sends photo + outfit image to Gemini image model
  -> returns a single JPEG try-on result
"""

import os
import traceback
from pathlib import Path
from io import BytesIO
from typing import List

from flask import Flask, request, jsonify, send_file, abort
from flask_cors import CORS
from PIL import Image
from dotenv import load_dotenv

from google import genai
from google.genai import types as genai_types

# -------------------------------------------------
# Paths / folders
# -------------------------------------------------

BASE_DIR = Path(r"C:\Users\Poorna\Desktop\VirtuWear_Project").resolve()

ASSETS_DIR = BASE_DIR / "assets"
IMG_DIR = ASSETS_DIR / "img_out"   # your garment images folder
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# -------------------------------------------------
# Environment & Gemini config
# -------------------------------------------------

load_dotenv(dotenv_path=BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-pro-image-preview") or ""
GEMINI_MODEL = GEMINI_MODEL.strip()  # remove accidental spaces/newlines
PORT = int(os.getenv("VIRTUWEAR_PORT", "5000"))

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. "
        "Open .env and set GEMINI_API_KEY=your_real_key_here."
    )

if not GEMINI_MODEL:
    raise RuntimeError(
        "GEMINI_MODEL is empty. Set GEMINI_MODEL in your .env "
        "(for example: gemini-2.5-flash-image)."
    )

print(f"[DEBUG] Using GEMINI_MODEL = {repr(GEMINI_MODEL)}")

client = genai.Client(api_key=GEMINI_API_KEY)

# -------------------------------------------------
# Flask app
# -------------------------------------------------

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")
CORS(app)


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTS


def list_outfits() -> List[str]:
    """Return a list of outfit filenames from assets/img_out."""
    if not IMG_DIR.exists():
        return []
    return sorted(
        [p.name for p in IMG_DIR.iterdir() if p.is_file() and allowed_file(p.name)]
    )


def find_outfit_path(name: str) -> Path:
    """
    Resolve outfit filename in assets/img_out by:
    - exact match
    - adding extensions
    - prefix matches
    """
    candidate = IMG_DIR / name
    if candidate.exists() and allowed_file(candidate.name):
        return candidate

    for ext in ALLOWED_EXTS:
        p = IMG_DIR / f"{name}{ext}"
        if p.exists():
            return p

    for p in IMG_DIR.glob(f"{name}*"):
        if p.is_file() and allowed_file(p.name):
            return p

    raise FileNotFoundError(f"Outfit not found: {name}")


def image_to_png_bytes(path: Path) -> bytes:
    """Load an image and return PNG bytes."""
    img = Image.open(path).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def run_gemini_tryon(user_path: Path, outfit_path: Path, extra_prompt: str = "") -> Path:
    """
    Send (user image + outfit image) to Gemini image model
    and save the resulting image into OUTPUT_DIR.
    """
    user_bytes = image_to_png_bytes(user_path)
    outfit_bytes = image_to_png_bytes(outfit_path)

    base_prompt = (
        "You are a professional virtual try-on system.\n"
        "Take the person from the first image (user photo) and realistically dress them in the "
        "clothing from the second image (outfit image).\n"
        "Keep the person's face, pose, body shape, skin tone, lighting, and background natural.\n"
        "Make the garment follow the body with realistic folds, shadows, and perspective.\n"
        "Return ONLY the final composited try-on image, no borders, no text, no collages."
    )
    if extra_prompt:
        base_prompt += "\nExtra styling instructions: " + extra_prompt

    contents = [
        genai_types.Content(
            parts=[
                genai_types.Part(text=base_prompt),
                genai_types.Part(
                    inline_data=genai_types.Blob(
                        mime_type="image/png",
                        data=user_bytes,
                    )
                ),
                genai_types.Part(
                    inline_data=genai_types.Blob(
                        mime_type="image/png",
                        data=outfit_bytes,
                    )
                ),
            ]
        )
    ]

    print(f"[DEBUG] Calling Gemini model: {repr(GEMINI_MODEL)}")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents
    )

    image_bytes = None

    if response and getattr(response, "candidates", None):
        for cand in response.candidates:
            content = getattr(cand, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []):
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    image_bytes = inline.data
                    break
            if image_bytes:
                break

    if image_bytes is None:
        raise RuntimeError(
            "Gemini did not return an image. "
            f"Model used: {GEMINI_MODEL}. Check the model ID in AI Studio "
            "and your project quota."
        )

    out_path = OUTPUT_DIR / "tryon_result_gemini.jpg"
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    img.save(out_path, format="JPEG", quality=95)
    return out_path


# -------------------------------------------------
# Routes
# -------------------------------------------------

@app.route("/")
def index():
    index_path = BASE_DIR / "index.html"
    if index_path.exists():
        return send_file(index_path)
    return "<h2>VirtuWear</h2><p>index.html not found.</p>", 404


@app.route("/assets/<path:filename>")
def serve_assets(filename):
    file_path = ASSETS_DIR / filename
    if file_path.exists():
        return send_file(file_path)
    abort(404)


@app.route("/api/outfits", methods=["GET"])
def api_outfits():
    try:
        files = list_outfits()
        return jsonify({"files": files})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/tryon", methods=["POST"])
def api_tryon():
    """
    Expects multipart/form-data:

      photo  -> uploaded user image
      outfit -> filename from /assets/img_out
      prompt -> optional text

    Returns: JPEG image binary (not JSON).
    """
    try:
        if "photo" not in request.files:
            return jsonify({"error": "Missing 'photo' file."}), 400

        photo = request.files["photo"]

        outfit_name = (
            request.form.get("outfit")
            or request.form.get("outfit_name")
            or request.args.get("outfit")
        )
        if not outfit_name:
            return jsonify({"error": "Missing 'outfit' parameter."}), 400

        prompt = request.form.get("prompt") or ""

        ext = Path(photo.filename).suffix.lower() or ".jpg"
        if ext not in ALLOWED_EXTS:
            ext = ".jpg"
        user_path = UPLOADS_DIR / f"user_photo{ext}"
        photo.save(str(user_path))

        try:
            outfit_path = find_outfit_path(outfit_name)
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 404

        result_path = run_gemini_tryon(user_path, outfit_path, prompt)
        return send_file(result_path, mimetype="image/jpeg")

    except Exception as e:
        traceback.print_exc()
        msg = str(e)
        if "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            msg = ("Gemini quota exhausted for this model. "
                   "Use a cheaper model or add billing in Google AI Studio.")
        return jsonify({"error": f"Try-on error: {msg}"}), 500


# -------------------------------------------------
# Main
# -------------------------------------------------

if __name__ == "__main__":
    print(f"VirtuWear server starting at http://127.0.0.1:{PORT}")
    print(f"Project root : {BASE_DIR}")
    print(f"Assets folder: {ASSETS_DIR}")
    print(f"Gemini model : {repr(GEMINI_MODEL)}")
    app.run(host="0.0.0.0", port=PORT, debug=True, threaded=True)
