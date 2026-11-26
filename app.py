import streamlit as st
import subprocess, os, re, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from youtube_transcript_api import YouTubeTranscriptApi

st.set_page_config(page_title="GTA Auto Clipper Web", page_icon="🎮", layout="wide")
st.title("🎮 GTA Auto Clipper — 9:16 Viral Shorts & Pop-Up Captions")

mode = st.radio("Video Source Chunein:", [
    "📤 Upload Gameplay Video (100% Guaranteed, No YouTube Block)",
    "🔗 YouTube Video URL (Auto-Fetch & Clip)"
])

clip_len = st.slider("Har Clip Ki Length (Seconds)", 15, 45, 25)
max_clips = st.slider("Kitne Clips Banane Hain?", 1, 5, 2)
yt_url = ""
uploaded_file = None

if "YouTube" in mode:
    yt_url = st.text_input("YouTube Gameplay Video Link Paste Karein:")
else:
    uploaded_file = st.file_uploader("Gameplay MP4 / MKV File Upload Karein (Max 200MB)", type=["mp4", "mkv", "mov"])

def extract_video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})", url)
    return m.group(1) if m else None

def find_hype_timestamps(video_path, num_clips, duration_sec):
    """Finds highest-energy audio spikes (explosions, shouting, hype reactions)."""
    clip = VideoFileClip(video_path)
    total_dur = clip.duration
    if total_dur <= duration_sec + 2:
        clip.close()
        return [0.0]

    audio = clip.audio
    if audio is None:
        clip.close()
        return [min(i * duration_sec, total_dur - duration_sec) for i in range(num_clips)]

    step = 2.0
    energies = []
    for t in np.arange(0, total_dur - duration_sec, step):
        sub = audio.subclip(t, min(t + step, total_dur))
        arr = sub.to_soundarray(fps=8000)
        rms = float(np.sqrt(np.mean(arr**2))) if len(arr) > 0 else 0
        energies.append((t, rms))
    clip.close()

    energies.sort(key=lambda x: x[1], reverse=True)
    chosen = []
    for t, _ in energies:
        start_t = max(0.0, t - 4.0)
        if all(abs(start_t - c) >= duration_sec for c in chosen):
            chosen.append(start_t)
        if len(chosen) >= num_clips:
            break
    return sorted(chosen) if chosen else [0.0]

def make_caption_frame(text, w=1080, h=1920):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 78)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (w - tw) // 2
    y = int(h * 0.72)

    # Black outline + Yellow pop-up text (GTA Clipper style)
    for dx in (-4, 0, 4):
        for dy in (-4, 0, 4):
            draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))
    draw.text((x, y), text, font=font, fill=(255, 230, 0, 255))
    return np.array(img)

def render_vertical_short(video_path, start_t, dur, transcript_items, out_path):
    base = VideoFileClip(video_path).subclip(start_t, min(start_t + dur, VideoFileClip(video_path).duration))
    # Center crop to 9:16 (1080x1920)
    target_ratio = 9 / 16
    w, h = base.size
    new_w = int(h * target_ratio)
    if new_w < w:
        x1 = (w - new_w) // 2
        base = base.crop(x1=x1, y1=0, x2=x1 + new_w, y2=h)
    base = base.resize((1080, 1920))

    layers = [base]
    # Add word-by-word pop-up captions from YouTube transcript if available
    for item in transcript_items:
        s_t = item["start"]
        e_t = s_t + item["duration"]
        if e_t < start_t or s_t > start_t + dur:
            continue
        words = item["text"].upper().split()
        if not words:
            continue
        w_dur = max(0.2, (e_t - s_t) / len(words))
        for idx, word in enumerate(words):
            ws = max(0, (s_t + idx * w_dur) - start_t)
            we = min(dur, ws + w_dur)
            if we > ws:
                frame = make_caption_frame(word)
                txt_clip = ImageClip(frame).set_start(ws).set_duration(we - ws)
                layers.append(txt_clip)

    final = CompositeVideoClip(layers)
    final.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", verbose=False, logger=None)
    final.close()
    base.close()

if st.button("🚀 Generate 9:16 Shorts"):
    os.makedirs("work", exist_ok=True)
    src_path = "work/source.mp4"
    transcript_data = []

    with st.spinner("1/3 Video load ho rahi hai..."):
        if "YouTube" in mode:
            if not yt_url:
                st.error("YouTube link paste karein.")
                st.stop()
            vid = extract_video_id(yt_url)
            try:
                transcript_data = YouTubeTranscriptApi.get_transcript(vid, languages=["en", "hi"])
            except Exception:
                transcript_data = []
            cmd = ["yt-dlp", "-f", "best[height<=720][ext=mp4]/best[ext=mp4]", "-o", src_path, "--force-overwrites", yt_url]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if not os.path.exists(src_path):
                st.error(f"YouTube ne cloud download block kiya. 'Upload Gameplay Video' option use karein!\nDetails: {res.stderr[:250]}")
                st.stop()
        else:
            if not uploaded_file:
                st.error("Gameplay video file upload karein.")
                st.stop()
            with open(src_path, "wb") as f:
                f.write(uploaded_file.read())

    with st.spinner("2/3 Audio hype moments dhoonde ja rahe hain..."):
        starts = find_hype_timestamps(src_path, max_clips, clip_len)

    for i, st_time in enumerate(starts, 1):
        out_file = f"work/gta_short_{i}.mp4"
        with st.spinner(f"3/3 Clip #{i} render ho raha hai (Start: {int(st_time)}s)..."):
            render_vertical_short(src_path, st_time, clip_len, transcript_data, out_file)
        st.success(f"✅ Short #{i} Ready! (Timestamp: {int(st_time)}s - {int(st_time + clip_len)}s)")
        st.video(out_file)
        with open(out_file, "rb") as vf:
            st.download_button(f"⬇️ Download Short #{i} (MP4)", vf, file_name=f"gta_short_{i}.mp4", mime="video/mp4")
