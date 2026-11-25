import os
import json
import requests
import arabic_reshaper

from bidi.algorithm import get_display
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# ================= CONFIG =================

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = "dexcexcrypto"

API = f"https://api.telegram.org/bot{TOKEN}"

BASE_DIR = Path("output")
BASE_DIR.mkdir(exist_ok=True)

STATE_FILE = Path("state.json")

WIDTH = 1080
HEIGHT = 1920

LINK = "t.me/dexcexcrypto"
BRAND = "DEXCEX CRYPTO"

FONT_PATH = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"

# ================= FONT =================

def get_font(size):
    if os.path.exists(FONT_PATH):
        return ImageFont.truetype(FONT_PATH, size)

    return ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        size
    )


def rtl(text):
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


# ================= STATE =================

def load_state():
    if STATE_FILE.exists():
        return json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

    return {"offset": 0}


def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state),
        encoding="utf-8"
    )


# ================= TELEGRAM =================

def get_updates(offset):

    response = requests.get(
        f"{API}/getUpdates",
        params={
            "offset": offset,
            "timeout": 10,
            "allowed_updates": json.dumps(["channel_post"])
        },
        timeout=25
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(data)

    return data["result"]


def download_file(file_id, destination):

    result = requests.get(
        f"{API}/getFile",
        params={"file_id": file_id},
        timeout=30
    )

    result.raise_for_status()

    data = result.json()

    if not data.get("ok"):
        raise RuntimeError("Telegram download error")

    file_path = data["result"]["file_path"]

    url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

    response = requests.get(url, timeout=120)
    response.raise_for_status()

    destination.write_bytes(response.content)

    return destination


# ================= DESIGN =================

def wrap_text(text, font, max_width):

    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)

    words = text.split()
    lines = []
    current = ""

    for word in words:

        test = f"{current} {word}".strip()
        shaped = rtl(test)

        box = draw.textbbox((0, 0), shaped, font=font)

        if box[2] - box[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)

            current = word

    if current:
        lines.append(current)

    return lines


def draw_text_rtl(draw, text, y, font, color):

    display_text = rtl(text)

    box = draw.textbbox(
        (0, 0),
        display_text,
        font=font
    )

    width = box[2] - box[0]

    x = WIDTH - 85 - width

    draw.text(
        (x, y),
        display_text,
        font=font,
        fill=color
    )


def create_story(text, filename, photo=None):

    if photo and photo.exists():

        image = Image.open(photo).convert("RGB")

        ratio = max(
            WIDTH / image.width,
            HEIGHT / image.height
        )

        new_size = (
            int(image.width * ratio),
            int(image.height * ratio)
        )

        image = image.resize(new_size)

        left = (image.width - WIDTH) // 2
        top = (image.height - HEIGHT) // 2

        image = image.crop((
            left,
            top,
            left + WIDTH,
            top + HEIGHT
        ))

        image = ImageEnhance.Brightness(image).enhance(0.55)

    else:

        image = Image.new(
            "RGB",
            (WIDTH, HEIGHT),
            (12, 19, 39)
        )

    draw = ImageDraw.Draw(image)

    # Header

    draw.rounded_rectangle(
        (55, 65, 1025, 245),
        radius=35,
        fill=(10, 28, 58)
    )

    brand_font = get_font(65)

    draw.text(
        (90, 110),
        BRAND,
        font=brand_font,
        fill=(70, 190, 255)
    )

    draw.line(
        (80, 285, 1000, 285),
        fill=(40, 160, 255),
        width=5
    )

    # News text

    font = get_font(52)

    lines = wrap_text(
        text,
        font,
        880
    )

    y = 420

    for line in lines[:15]:

        draw_text_rtl(
            draw,
            line,
            y,
            font,
            "white"
        )

        y += 85

    # Footer

    draw.rounded_rectangle(
        (55, 1650, 1025, 1835),
        radius=35,
        fill=(10, 28, 58)
    )

    footer_font = get_font(42)

    draw.text(
        (90, 1680),
        "TELEGRAM CHANNEL",
        font=get_font(30),
        fill=(80, 180, 255)
    )

    draw.text(
        (90, 1740),
        LINK,
        font=footer_font,
        fill="white"
    )

    output = BASE_DIR / filename

    image.save(output, quality=95)

    return output


# ================= PROCESS =================

def process_post(post):

    post_id = post["message_id"]

    folder = BASE_DIR / str(post_id)
    folder.mkdir(parents=True, exist_ok=True)

    content = (
        post.get("text")
        or post.get("caption")
        or ""
    )

    photo_path = None

    # Photo

    if post.get("photo"):

        photo = post["photo"][-1]

        photo_path = download_file(
            photo["file_id"],
            folder / "source.jpg"
        )

    # Video

    elif post.get("video"):

        video = post["video"]

        download_file(
            video["file_id"],
            folder / "source.mp4"
        )

        print("VIDEO DOWNLOADED:", post_id)

        return

    # Generate story

    if content or photo_path:

        create_story(
            content or "DEXCEX CRYPTO",
            f"{post_id}.png",
            photo_path
        )

        print("STORY CREATED:", post_id)

    (folder / "caption.txt").write_text(
        content,
        encoding="utf-8"
    )


# ================= MAIN =================

def main():

    state = load_state()

    offset = state.get("offset", 0)

    print("DEXCEX AUTO STORY STARTED")

    updates = get_updates(offset)

    for update in updates:

        new_offset = update["update_id"] + 1

        post = update.get("channel_post")

        if not post:
            offset = new_offset
            continue

        username = (
            post.get("chat", {})
            .get("username", "")
            .lower()
        )

        if username != CHANNEL:
            offset = new_offset
            continue

        process_post(post)

        offset = new_offset

        state["offset"] = offset

        save_state(state)

    print("FINISHED")


if __name__ == "__main__":
    main()
