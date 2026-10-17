#!/usr/bin/env python3
"""Robi pionowy short 1080x1920 z klipu w układzie jak wzór "PO_AR_W_CHACIE":

  [ kamerka            0-773 ]
  [ czerwony napis na styku  ]
  [ gra               773-1565 ]   <- logo TSXNINE na dolnej krawędzi gry
  [ rozmyte tło       1565-1920 ]

Użycie:
  python3 short.py --clip https://kick.com/mamm0n/clips/clip_XXXX --caption "MGŁA NA NUKE" --out short.mp4
  python3 short.py --input klip.mp4 --caption "..." --cam 0,0,0.26,0.33

--cam x,y,w,h = gdzie w klipie jest kamerka, jako ułamki klatki (0-1).
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

# --- układ (zmierzony na wzorze) ---
W, H = 1080, 1920
CAM_H = 773                 # wysokość sekcji z kamerką
GAME_Y, GAME_H = 773, 792   # sekcja z grą: y 773..1565
BOX_X0, BOX_X1 = 54, 1025   # maks. szerokość czerwonego paska
BOX_CY_NOCAM = 360          # pasek w trybie bez kamerki (wyżej)
BOX_CY = 740                # środek paska (lekko nad stykiem kamery i gry)
LOGO_CX, LOGO_CY = 565, 1565  # środek logo: na dolnej krawędzi gry
HERE = os.path.dirname(os.path.abspath(__file__))

# Logo TSXNINE (PNG z przezroczystością) wbudowane w skrypt; jeśli obok leży plik logo.png, ma pierwszeństwo.
EMBEDDED_LOGO = (
    "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"
    "AAAAAElFTkSuQmCC"
)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def find_font(custom):
    for p in ([custom] if custom else []) + FONTS:
        if p and os.path.exists(p):
            return p
    sys.exit("Nie znaleziono czcionki. Podaj --font ścieżka.ttf")


TWITCH_GQL = "https://gql.twitch.tv/gql"
TWITCH_CID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
TWITCH_RE = re.compile(r"(?:clips\.twitch\.tv/(?:embed\?clip=)?|twitch\.tv/[A-Za-z0-9_]+/clip/)([A-Za-z0-9_\-]+)")


def resolve_twitch(slug):
    """Twitch: slug klipu -> bezpośredni adres mp4 z podpisem."""
    body = [{
        "operationName": "VideoAccessToken_Clip",
        "variables": {"platform": "web", "slug": slug},
        "extensions": {"persistedQuery": {"version": 1,
            "sha256Hash": "36b89d2507fce29e5ca551df756d27c1cfe079e2609642b4390aa4c35796eb11"}},
    }]
    req = urllib.request.Request(TWITCH_GQL, data=json.dumps(body).encode(),
        headers={"Client-ID": TWITCH_CID, "Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    clip = (data[0].get("data") or {}).get("clip")
    if not clip or not clip.get("videoQualities"):
        sys.exit("Twitch nie zwrócił klipu (zły link albo klip usunięty).")
    best = max(clip["videoQualities"], key=lambda q: float(q.get("quality") or 0))
    tok = clip["playbackAccessToken"]
    return f"{best['sourceURL']}?sig={tok['signature']}&token={urllib.parse.quote(tok['value'], safe='')}"


def resolve_clip(clip, proxy):
    """Link do klipu (Kick albo Twitch) -> adres wideo."""
    t = TWITCH_RE.search(clip)
    if t and "kick.com" not in clip:
        return resolve_twitch(t.group(1))
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


def probe(path, pre=()):
    out = subprocess.run(
        ["ffprobe", "-v", "error", *pre, "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0:s=x", path],
        capture_output=True, text=True)
    if out.returncode != 0 or "x" not in out.stdout:
        sys.exit("Nie mogę otworzyć wideo (zablokowane lub zły adres):\n" + out.stderr[-300:])
    w, h = out.stdout.strip().split("\n")[0].split("x")[:2]
    return int(w), int(h)


def media_info(path, pre=()):
    """(czas trwania w s, czy jest dźwięk)"""
    d = subprocess.run(["ffprobe", "-v", "error", *pre, "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    a = subprocess.run(["ffprobe", "-v", "error", *pre, "-select_streams", "a:0", "-show_entries",
                        "stream=codec_type", "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        dur = float(d.stdout.strip().split("\n")[0])
    except ValueError:
        dur = 0.0
    return dur, bool(a.stdout.strip())


def speech_segments(path, pre, dur, noise_db=-32, min_sil=0.7, pad=0.15):
    """Zwraca listę (start, koniec) fragmentów do zostawienia; ciszę dłuższą niż min_sil skraca,
    zostawiając po 'pad' sekund z każdej strony, żeby nie ucinać słów."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *pre, "-i", path, "-vn",
                        "-af", f"silencedetect=noise={noise_db}dB:d={min_sil}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: (-?[0-9.]+)", r.stderr)]
    sil = []
    for i, st in enumerate(starts):
        en = ends[i] if i < len(ends) else dur
        st = max(st, 0.0)
        a, b = st + pad, en - pad
        if b - a > 0.05:
            sil.append((a, b))
    if not sil:
        return None
    keep, cur = [], 0.0
    for a, b in sil:
        if a > cur:
            keep.append((cur, a))
        cur = b
    if cur < dur:
        keep.append((cur, dur))
    keep = [(a, b) for a, b in keep if b - a > 0.1]
    removed = dur - sum(b - a for a, b in keep)
    print(f"Cisza: wycinam {removed:.1f} s z {dur:.1f} s ({len(keep)} fragmentów)")
    return keep if removed >= 0.5 and keep else None


# ---------- napisy (Whisper), głośność, przycinanie ----------
def extract_wav(source, pre, out):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *pre, "-i", source,
                        "-vn", "-ac", "1", "-ar", "16000", out], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("Nie mogę wyciągnąć dźwięku do rozpoznawania mowy:\n" + r.stderr[-300:])


def transcribe(source, pre, tmp, lang="pl", model_name="small"):
    """Zwraca (słowa [(start, koniec, tekst)], frazy [tekst]) z rozpoznawania mowy (faster-whisper)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("Brak biblioteki faster-whisper (pip install faster-whisper).")
    wav = os.path.join(tmp, "audio.wav")
    extract_wav(source, pre, wav)
    # dźwięk wczytujemy sami (omija błąd modułu 'av' w faster-whisper)
    import wave
    import numpy as np
    with wave.open(wav, "rb") as wf:
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = model.transcribe(audio, language=lang or None, word_timestamps=True,
                                  vad_filter=True, beam_size=1)
    words, phrases = [], []
    for sg in segs:
        phrases.append(sg.text.strip())
        for w in sg.words or []:
            t = w.word.strip()
            if t:
                words.append((float(w.start), float(w.end), t))
    print(f"Rozpoznano {len(words)} słów (język: {getattr(info, 'language', '?')}).")
    return words, phrases


def load_words(path):
    d = json.load(open(path, encoding="utf-8"))
    words = [(float(w[0]), float(w[1]), str(w[2])) for w in d["words"]]
    return words, d.get("phrases", [])


def remap_words(words, segs, limit):
    """Przelicza czasy słów na czasy filmu po wycięciach; odrzuca słowa z wyciętych miejsc."""
    out, off = [], 0.0
    for a, b in segs:
        for st, en, t in words:
            if a - 0.01 <= st < b:
                out.append((off + (st - a), off + (min(en, b) - a), t))
        off += b - a
    return [w for w in out if w[0] < limit]


def ass_time(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_ass(path, words, font_name="DejaVu Sans", y_bottom=H // 2, size=76):
    """Napisy w stylu TikToka: 2-3 słowa naraz, aktualnie mówione słowo na żółto."""
    groups, cur = [], []
    for w in words:
        if cur and (len(cur) >= 3 or w[0] - cur[-1][1] > 0.6
                    or len(" ".join(x[2] for x in cur + [w])) > 22):
            groups.append(cur)
            cur = []
        cur.append(w)
    if cur:
        groups.append(cur)

    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: %d\nPlayResY: %d\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
        "Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        "Style: Default,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,2,5,60,60,%d,1\n\n"
        "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    ) % (W, H, font_name, size, 0)
    lines = []
    for g in groups:
        for i, (st, en, _) in enumerate(g):
            end = g[i + 1][0] if i + 1 < len(g) else max(en, st + 0.2) + 0.15
            if end <= st:
                end = st + 0.1
            txt = " ".join(
                ("{\\c&H00FFFF&}%s{\\c&HFFFFFF&}" if j == i else "%s") % x[2].upper().replace("{", "(").replace("}", ")")
                for j, x in enumerate(g))
            lines.append(f"Dialogue: 0,{ass_time(st)},{ass_time(end)},Default,,0,0,0,,{txt}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")


def suggest_captions(phrases, words):
    """Proponuje do 3 krótkich napisów do czerwonego paska na podstawie tego, co padło w klipie."""
    cands = []
    for ph in phrases:
        for part in re.split(r"(?<=[.!?…])\s+|,\s+", ph):
            part = part.strip(" .,;:-–—")
            if 6 <= len(part) <= 40:
                cands.append(part)
    if not cands and words:  # brak zdań: bierz po 3-4 słowa
        toks = [w[2] for w in words]
        cands = [" ".join(toks[i:i + 4]) for i in range(0, min(len(toks), 12), 4)]

    def score(c):
        sc = 0.0
        if re.search(r"\d", c): sc += 2
        if "!" in c or "?" in c: sc += 1.5
        sc -= abs(len(c) - 20) / 10
        sc += max(0, 1 - cands.index(c) / max(1, len(cands))) * 0.7  # wcześniejsze lekko wyżej
        return sc

    out = []
    for c in sorted(set(cands), key=score, reverse=True):
        c = re.sub(r"[!?.…]+$", "", c).upper()
        if c and c not in out:
            out.append(c)
        if len(out) == 3:
            break
    return out


def plan_segments(dur, start, end, silence):
    """Lista (od, do) fragmentów źródła do zostawienia (po przycięciu i ewentualnym wycięciu ciszy)."""
    lo = max(0.0, start)
    hi = min(dur, end) if end and end > 0 else dur
    if hi <= lo:
        sys.exit("Koniec fragmentu jest przed początkiem.")
    base = [(lo, hi)]
    if silence:
        out = []
        for a, b in silence:
            a2, b2 = max(a, lo), min(b, hi)
            if b2 - a2 > 0.1:
                out.append((a2, b2))
        base = out or base
    if base == [(0.0, dur)]:
        return None
    return base


def tlen(draw, text, font):
    return draw.textlength(text, font=font) + 10  # + obrys


def _wrap(draw, words, font, max_w):
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if tlen(draw, trial, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def fit_text(draw, text, font_path, max_w):
    """Najpierw próbuje zmieścić napis w jednej linii (czcionka 112 -> 64), potem w dwóch."""
    words = text.split()
    for max_lines, lo in ((1, 64), (2, 40)):
        for size in range(104, lo - 1, -2):
            font = ImageFont.truetype(font_path, size)
            lines = _wrap(draw, words, font, max_w)
            if len(lines) <= max_lines and all(tlen(draw, l, font) <= max_w for l in lines):
                return font, lines
    return ImageFont.truetype(font_path, 40), [text[:50]]


def render_overlay(path, caption, font_path, logo_path, cap_cy=None):
    cap_cy = BOX_CY if cap_cy is None else cap_cy
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if caption:
        text = caption.upper()
        font, lines = fit_text(d, text, font_path, (BOX_X1 - BOX_X0) - 60)
        asc, desc = font.getmetrics()
        line_h = int((asc + desc) * 0.98)
        tw = max(tlen(d, l, font) for l in lines)
        box_w = int(min(tw + 60, BOX_X1 - BOX_X0))
        box_h = int(max(132, line_h * len(lines) + 24))
        cx = (BOX_X0 + BOX_X1) // 2
        x0, y0 = cx - box_w // 2, cap_cy - box_h // 2
        d.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=(226, 18, 18, 255))
        # tekst pionowo na środku paska
        block_h = line_h * len(lines)
        ty = y0 + (box_h - block_h) // 2 - int(font.size * 0.06)
        for i, l in enumerate(lines):
            lw = d.textlength(l, font=font)
            d.text((cx - lw / 2, ty + i * line_h), l, font=font, fill="white",
                   stroke_width=5, stroke_fill="black")

    logo = None
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
    elif logo_path is not None and logo_path != "":
        import base64, io
        logo = Image.open(io.BytesIO(base64.b64decode(EMBEDDED_LOGO))).convert("RGBA")
    if logo is not None:
        img.alpha_composite(logo, (LOGO_CX - logo.width // 2, LOGO_CY - logo.height // 2))

    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--clip", help="link do klipu na Kicku albo Twitchu")
    src.add_argument("--input", help="plik wideo albo adres m3u8")
    ap.add_argument("--caption", default="", help="napis w czerwonym pasku")
    ap.add_argument("--logo", default=os.path.join(HERE, "logo.png"),
                    help="obrazek na dolnej krawędzi gry (PNG z przezroczystością); '' = bez logo")
    ap.add_argument("--no-logo", action="store_true", help="bez logo TSXNINE")
    ap.add_argument("--no-cam", action="store_true", help="bez kamerki: gra na cały ekran")
    ap.add_argument("--captions", action="store_true", help="napisy słowo po słowie (Whisper)")
    ap.add_argument("--lang", default="pl", help="język mowy do napisów (pl, en, '' = automatycznie)")
    ap.add_argument("--volume", type=float, default=1.0, help="głośność dźwięku (1 = bez zmian)")
    ap.add_argument("--start", type=float, default=0.0, help="początek fragmentu (s)")
    ap.add_argument("--end", type=float, default=0.0, help="koniec fragmentu (s), 0 = do końca")
    ap.add_argument("--words-json", default="", help="gotowe słowa zamiast Whisper (do testów)")
    ap.add_argument("--suggest", default="", help="tylko zaproponuj napisy i zapisz do tego pliku JSON")
    ap.add_argument("--cut-silence", action="store_true", help="wytnij fragmenty, w których nikt nic nie mówi")
    ap.add_argument("--cam", default="0,0,0.26,0.33", help="x,y,w,h kamerki jako ułamki klatki")
    ap.add_argument("--game", default="", help="x,y,w,h gry jako ułamki (domyślnie środek klatki)")
    ap.add_argument("--proxy", default=os.environ.get("KICK_PROXY", ""), help="adres Workera kick-proxy")
    ap.add_argument("--font", default="")
    ap.add_argument("--out", default="short.mp4")
    ap.add_argument("--max-seconds", type=int, default=180, help="maks. długość filmu (0 = 180)")
    a = ap.parse_args()

    source = resolve_clip(a.clip, a.proxy) if a.clip else a.input
    print("Źródło:", source)

    pre = []
    if source.startswith("http") and "twitch" not in source:
        pre = ["-user_agent", UA, "-headers", "Referer: https://kick.com/\r\n"]
    sw, sh = probe(source, pre)

    cx, cy, cw, ch = [float(v) for v in a.cam.split(",")]
    if a.game:
        gx, gy, gw, gh = [float(v) for v in a.game.split(",")]
    else:  # pełna wysokość, środek klatki, proporcje sekcji gry
        gh, gy = 1.0, 0.0
        gw = min(((W / H) if a.no_cam else (W / GAME_H)) * sh / sw, 1.0)
        gx = (1 - gw) / 2

    tmp = tempfile.mkdtemp()

    # --- tryb propozycji napisów: tylko rozpoznanie mowy ---
    if a.suggest:
        words, phrases = load_words(a.words_json) if a.words_json else transcribe(source, pre, tmp, a.lang)
        data = {"suggestions": suggest_captions(phrases, words),
                "text": " ".join(w[2] for w in words)[:600],
                "words": [[round(x[0], 2), round(x[1], 2), x[2]] for x in words],
                "phrases": phrases}
        with open(a.suggest, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        print("Propozycje:", data["suggestions"])
        return

    overlay = os.path.join(tmp, "overlay.png")
    render_overlay(overlay, a.caption, find_font(a.font), "" if a.no_logo else a.logo,
                   BOX_CY_NOCAM if a.no_cam else BOX_CY)

    limit = a.max_seconds if a.max_seconds and a.max_seconds > 0 else 180
    dur, has_audio = media_info(source, pre)
    silence = None
    if a.cut_silence:
        if has_audio and dur > 0:
            kept = speech_segments(source, pre, dur)
            silence = kept  # fragmenty, w których ktoś mówi
            if not kept:
                print("Cisza: nic do wycięcia.")
        else:
            print("Cisza: brak dźwięku, pomijam.")
    segs = plan_segments(dur, a.start, a.end, silence) if dur > 0 else None

    words = []
    if a.captions:
        if not has_audio:
            print("Napisy: brak dźwięku, pomijam.")
        else:
            words, _ = load_words(a.words_json) if a.words_json else transcribe(source, pre, tmp, a.lang)
            words = remap_words(words, segs or [(0.0, dur or 1e9)], limit)
            print(f"Napisy: {len(words)} słów.")
    ass_path = os.path.join(tmp, "napisy.ass")
    if words:
        write_ass(ass_path, words)

    head, vin, ain = "", "[0:v]", "[0:a]"
    if segs:
        parts = []
        for i, (t0, t1) in enumerate(segs):
            parts.append(f"[0:v]trim=start={t0:.3f}:end={t1:.3f},setpts=PTS-STARTPTS[v{i}];")
            if has_audio:
                parts.append(f"[0:a]atrim=start={t0:.3f}:end={t1:.3f},asetpts=PTS-STARTPTS[a{i}];")
        n = len(segs)
        if has_audio:
            head = "".join(parts) + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac];"
            vin, ain = "[vc]", "[ac]"
        else:
            head = "".join(parts) + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc];"
            vin = "[vc]"
    amap = ain if (segs and has_audio) else "0:a?"
    if has_audio and abs(a.volume - 1.0) > 0.01:
        vol = max(0.0, min(a.volume, 5.0))
        head += f"{ain}volume={vol:.3f}[ao];"
        amap = "[ao]"

    subs = f",ass='{ass_path}'" if words else ""
    if a.no_cam:
        fc = head + (
            f"{vin}crop=trunc(iw*{gw}):trunc(ih*{gh}):trunc(iw*{gx}):trunc(ih*{gy}),"
            f"scale={W}:{H},setsar=1[g];"
            f"[g][1:v]overlay=0:0:shortest=1{subs},format=yuv420p[v]"
        )
    else:
        fc = head + (
            f"{vin}split=3[a][b][c];"
            # rozmyte tło na całą klatkę (liczone na małym obrazie, potem powiększone)
            "[a]scale=270:480:force_original_aspect_ratio=increase,crop=270:480,"
            f"gblur=sigma=9,scale={W}:{H}:flags=bicubic,setsar=1[bg];"
            f"[b]crop=trunc(iw*{cw}):trunc(ih*{ch}):trunc(iw*{cx}):trunc(ih*{cy}),"
            f"scale={W}:{CAM_H},setsar=1[cam];"
            f"[c]crop=trunc(iw*{gw}):trunc(ih*{gh}):trunc(iw*{gx}):trunc(ih*{gy}),"
            f"scale={W}:{GAME_H},setsar=1[game];"
            "[bg][cam]overlay=0:0[t1];"
            f"[t1][game]overlay=0:{GAME_Y}[t2];"
            f"[t2][1:v]overlay=0:0:shortest=1{subs},format=yuv420p[v]"
        )
    cmd = (["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + pre + ["-i", source,
           "-loop", "1", "-framerate", "30", "-i", overlay,
           "-filter_complex", fc, "-map", "[v]", "-map", amap,
           "-t", str(limit),
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", a.out])
    subprocess.run(cmd, check=True)
    print("Gotowe:", a.out)


if __name__ == "__main__":
    main()
