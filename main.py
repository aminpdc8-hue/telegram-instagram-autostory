
import os
import json
import time
import requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ========== CONFIG ==========

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = "@dexcexcrypto"

API = f"https://api.telegram.org/bot{TOKEN}"
BASE_DIR = Path("output")
BASE_DIR.mkdir(exist_ok=True)

STATE_FILE = Path("state.json")

# ========== STATE ==========

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"offset": 0}

def save_state(state):
    STATE_FILE.write_text(
        json.dumps(state),
        encoding="utf-8"
    )

# ========== TELEGRAM ==========

def get_updates(offset):
    response = requests.get(
        f"{API}/getUpdates",
        params={
            "offset": offset,
            "timeout": 10,
            "allowed_updates": json.dumps(["channel_post"])
        },
        timeout=20
    )
    response.raise_for_status()
    return response.json()["result"]

def download_file(file_id, filename):
    result = requests.get(
        f"{API}/getFile",
        params={"file_id": file_id},
        timeout=30
    ).json()

    if not result.get("ok"):
        raise RuntimeError("Telegram file lookup failed")

    file_path = result["result"]["file_path"]

    url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"

    data = requests.get(url, timeout=120)
    data.raise_for_status()

    path = BASE_DIR / filename
    path.write_bytes(data.content)

    return path

# ========== TEXT STORY ==========

def create_story(text, filename):

    image = Image.new(
        "RGB",
        (1080, 1920),
        (15, 20, 35)
    )

    draw = ImageDraw.Draw(image)

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    font = ImageFont.truetype(font_path, 45)

    lines = []
    words = text.split()
    line = ""

    for word in words:
        test = line + " " + word

        if draw.textlength(test, font=font) < 900:
            line = test
        else:
            lines.append(line)
            line = word

    if line:
        lines.append(line)

    y = 400

    for line in lines:
        draw.text(
            (90, y),
            line,
            font=font,
            fill="white"
        )
        y += 75

    draw.text(
        (90, 1700),
        "DEXCEX CRYPTO",
        font=font,
        fill=(80, 180, 255)
    )

    path = BASE_DIR / filename
    image.save(path)

    return path

# ========== PROCESS POSTS ==========

def process_post(post):

    post_id = post["message_id"]

    folder = BASE_DIR / str(post_id)
    folder.mkdir(exist_ok=True)

    caption = post.get("caption", "")
    text = post.get("text", "")

    content = caption or text

    if post.get("photo"):

        photo = post["photo"][-1]

        download_file(
            photo["file_id"],
            f"{post_id}.jpg"
        )

        print("PHOTO:", post_id)

    elif post.get("video"):

        download_file(
            post["video"]["file_id"],
            f"{post_id}.mp4"
        )

        print("VIDEO:", post_id)

    elif content:

        create_story(
            content,
            f"{post_id}.png"
        )

        print("TEXT:", post_id)

    (folder / "caption.txt").write_text(
        content,
        encoding="utf-8"
    )

# ========== MAIN ==========

def main():

    state = load_state()
    offset = state["offset"]

    print("AUTO STORY BOT STARTED")

    updates = get_updates(offset)

    for update in updates:

        offset = update["update_id"] + 1

        post = update.get("channel_post")

        if not post:
            continue

        if post.get("chat", {}).get("username", "").lower() != CHANNEL[1:].lower():
            continue

        try:
            process_post(post)

        except Exception as error:
            print("ERROR:", error)

        state["offset"] = offset
        save_state(state)

    print("FINISHED")

if __name__ == "__main__":
    main()
