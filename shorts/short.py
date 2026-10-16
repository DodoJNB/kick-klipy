#!/usr/bin/env python3
"""Robi pionowy short (1080x1920) z klipu: kamerka u góry, gra na dole, czerwony napis na styku.

Użycie:
  python3 short.py --clip https://kick.com/mamm0n/clips/clip_XXXX --caption "MGŁA NA NUKE" --out short.mp4
  python3 short.py --input klip.mp4 --caption "..." --cam 0,0,0.26,0.33

Układ źródła (gdzie jest kamerka) ustawiasz przez --cam x,y,w,h jako ułamki klatki (0-1).
Wymaga: ffmpeg, Pillow (pip install pillow).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def find_font(custom):
    for p in ([custom] if custom else []) + FONTS:
        if p and os.path.exists(p):
            return p
    sys.exit("Nie znaleziono czcionki. Podaj --font ścieżka.ttf")


def resolve_clip(clip, proxy):
    """Kick: link do klipu -> adres playlisty m3u8 (przez proxy, bo Kick blokuje serwery)."""
    m = re.search(r"(clip_[A-Za-z0-9]+)", clip)
    if not m:
        sys.exit("Nie widzę ID klipu (clip_...) w linku.")
    api = f"https://kick.com/api/v2/clips/{m.group(1)}"
    url = f"{proxy}?url={urllib.parse.quote(api, safe='')}" if proxy else api
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    c = data.get("clip", data)
    src = c.get("video_url") or c.get("clip_url")
    if not src:
        sys.exit("API Kicka nie zwróciło adresu wideo.")
    return src


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0:s=x", path],
        capture_output=True, text=True, check=True).stdout.strip()
    w, h = out.split("x")
    return int(w), int(h)


def tlen(draw, text, font):
    return draw.textlength(text, font=font) + 8  # + obrys


def fit_text(draw, text, font_path, max_w, max_lines=3):
    """Dobiera największy rozmiar czcionki, przy którym napis mieści się w max_w w max_lines liniach."""
    words = text.split()
    for size in range(120, 39, -4):
        font = ImageFont.truetype(font_path, size)
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if tlen(draw, trial, font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        if len(lines) <= max_lines and all(tlen(draw, l, font) <= max_w for l in lines):
            return font, lines
    return ImageFont.truetype(font_path, 40), [text[:60]]


def render_overlay(path, caption, seam_y, font_path, watermark):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if caption:
        text = caption.upper()
        font, lines = fit_text(d, text, font_path, W - 160)
        asc, desc = font.getmetrics()
        line_h = asc + desc
        tw = max(tlen(d, l, font) for l in lines)
        box_w, box_h = int(tw + 70), int(line_h * len(lines) + 40)
        x0, y0 = (W - box_w) // 2, seam_y - box_h // 2
        d.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(226, 18, 18, 255))
        for i, l in enumerate(lines):
            lw = tlen(d, l, font)
            d.text(((W - lw) / 2, y0 + 20 + i * line_h), l, font=font, fill="white",
                   stroke_width=4, stroke_fill="black")

    if watermark:
        f = ImageFont.truetype(font_path, 44)
        ww = d.textlength(watermark, font=f) + 4
        d.text((W - ww - 36, H - 110), watermark, font=f, fill=(255, 255, 255, 190),
               stroke_width=2, stroke_fill=(0, 0, 0, 160))

    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--clip", help="link do klipu na Kicku")
    src.add_argument("--input", help="plik wideo albo adres m3u8")
    ap.add_argument("--caption", default="", help="napis w czerwonym pasku")
    ap.add_argument("--watermark", default="", help="mały napis w rogu, np. @nick")
    ap.add_argument("--cam", default="0,0,0.26,0.33", help="x,y,w,h kamerki jako ułamki klatki")
    ap.add_argument("--cam-height", type=int, default=760, help="wysokość sekcji z kamerką w pikselach")
    ap.add_argument("--game", default="", help="x,y,w,h gry jako ułamki (domyślnie środek klatki)")
    ap.add_argument("--proxy", default=os.environ.get("KICK_PROXY", ""), help="adres Workera kick-proxy")
    ap.add_argument("--font", default="")
    ap.add_argument("--out", default="short.mp4")
    ap.add_argument("--max-seconds", type=int, default=180)
    a = ap.parse_args()

    source = resolve_clip(a.clip, a.proxy) if a.clip else a.input
    print("Źródło:", source)

    # przy adresach http ffmpeg dostaje nagłówki jak przeglądarka
    pre = []
    if source.startswith("http"):
        pre = ["-user_agent", UA, "-headers", "Referer: https://kick.com/\r\n"]
        sw, sh = probe_remote(source, pre)
    else:
        sw, sh = probe(source)

    cam_h = a.cam_height
    game_h = H - cam_h
    cx, cy, cw, ch = [float(v) for v in a.cam.split(",")]
    if a.game:
        gx, gy, gw, gh = [float(v) for v in a.game.split(",")]
    else:  # pełna wysokość, środek klatki, proporcje sekcji gry
        gh, gy = 1.0, 0.0
        gw = (W / game_h) * sh / sw
        gx = (1 - gw) / 2
        gw = min(gw, 1.0)

    font_path = find_font(a.font)
    tmp = tempfile.mkdtemp()
    overlay = os.path.join(tmp, "overlay.png")
    render_overlay(overlay, a.caption, cam_h, font_path, a.watermark)

    fc = (
        "[0:v]split=2[a][b];"
        f"[a]crop=trunc(iw*{cw}):trunc(ih*{ch}):trunc(iw*{cx}):trunc(ih*{cy}),"
        f"scale={W}:{cam_h},setsar=1[cam];"
        f"[b]crop=trunc(iw*{gw}):trunc(ih*{gh}):trunc(iw*{gx}):trunc(ih*{gy}),"
        f"scale={W}:{game_h},setsar=1[game];"
        "[cam][game]vstack=inputs=2[stack];"
        "[stack][1:v]overlay=0:0:shortest=1,fps=30,format=yuv420p[v]"
    )
    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + pre + ["-i", source,
           "-loop", "1", "-framerate", "30", "-i", overlay,
           "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
           "-t", str(a.max_seconds),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", a.out])
    subprocess.run(cmd, check=True)
    print("Gotowe:", a.out)


def probe_remote(url, pre):
    out = subprocess.run(
        ["ffprobe", "-v", "error"] + pre + ["-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0:s=x", url],
        capture_output=True, text=True)
    if out.returncode != 0 or "x" not in out.stdout:
        sys.exit("Nie mogę otworzyć wideo (zablokowane lub zły adres):\n" + out.stderr[-300:])
    w, h = out.stdout.strip().split("\n")[0].split("x")[:2]
    return int(w), int(h)


if __name__ == "__main__":
    main()
