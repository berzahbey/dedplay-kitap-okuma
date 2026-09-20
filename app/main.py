import os
import re
import json
from urllib.parse import quote
import subprocess
import requests
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
import mimetypes
mimetypes.add_type('audio/mp4', '.m4b')
mimetypes.add_type('audio/mp4', '.m4a')
import fitz
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from pydub import AudioSegment

from app.cleaner import TextNormalizer
from app.lang_router import group_by_language

app = FastAPI(title="Dedplay Kitap Okuma")


BOOKS_DIR = Path("/app/books")
AUDIO_DIR = Path("/app/audio")
MODEL_DIR = Path("/root/.cache/piper")
BOOKS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

job_status = {}

VOICES = {
    "tr": {"name": "tr_TR-dfki-medium",
           "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx",
           "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx.json"},
    "en": {"name": "en_US-lessac-medium",
           "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
           "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"},
    "fr": {"name": "fr_FR-siwis-medium",
           "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx",
           "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"},
    "ar": {"name": "ar_JO-kareem-medium",
           "onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx",
           "json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json"},
}

def ensure_voice_model(lang: str) -> str:
    voice = VOICES[lang]
    onnx_path = MODEL_DIR / f"{voice['name']}.onnx"
    json_path = MODEL_DIR / f"{voice['name']}.onnx.json"
    if not onnx_path.exists():
        r = requests.get(voice["onnx"]); onnx_path.write_bytes(r.content)
    if not json_path.exists():
        r = requests.get(voice["json"]); json_path.write_bytes(r.content)
    return str(onnx_path)

def synthesize_block(text: str, lang: str, out_wav: Path):
    model_file = ensure_voice_model(lang)
    cmd = ["piper", "--model", model_file, "--output_file", str(out_wav)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate(input=text)
    if process.returncode != 0:
        raise RuntimeError(f"Piper error ({lang}): {stderr}")

def synthesize_chapter(text: str, output_path: Path):
    blocks = group_by_language(text)
    if not blocks:
        return
    combined = AudioSegment.silent(duration=0)
    silence_gap = AudioSegment.silent(duration=180)
    tmp_dir = output_path.parent / f".tmp_{output_path.stem}"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for i, (lang, block_text) in enumerate(blocks):
            part_wav = tmp_dir / f"part_{i:03d}.wav"
            synthesize_block(block_text, lang, part_wav)
            seg = AudioSegment.from_wav(part_wav)
            combined += seg + silence_gap
        raw_wav = output_path.with_suffix('.raw.wav')
        combined.export(raw_wav, format="wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", str(raw_wav),
            "-codec:a", "libmp3lame", "-b:a", "192k",
            "-filter:a", "loudnorm=I=-16:TP=-1.5:LRA=11",
            str(output_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raw_wav.unlink(missing_ok=True)
    finally:
        for f in tmp_dir.glob("*"):
            f.unlink()
        tmp_dir.rmdir()

def get_duration_ms(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True
    )
    data = json.loads(result.stdout)
    return int(float(data["format"]["duration"]) * 1000)

def natural_key(path: Path):
    m = re.match(r"(?:Bolum|Parca)_(\d+)", path.stem)
    return int(m.group(1)) if m else 0

def build_audiobook(book_dir: Path, book_title: str):
    mp3_files = sorted(
        [p for p in book_dir.glob("*.mp3")],
        key=natural_key
    )
    if not mp3_files:
        return None

    concat_list = book_dir / "_concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in mp3_files:
            f.write(f"file \'{p.name}\'\n")

    concat_mp3 = book_dir / "_full_concat.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(concat_mp3)
    ], check=True, cwd=str(book_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    meta_path = book_dir / "_chapters.txt"
    cursor_ms = 0
    lines = [";FFMETADATA1"]
    for p in mp3_files:
        dur_ms = get_duration_ms(p)
        title = re.sub(r"^(Bolum|Parca)_\d+_?", "", p.stem).replace("_", " ").strip() or p.stem
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={cursor_ms}")
        lines.append(f"END={cursor_ms + dur_ms}")
        lines.append(f"title={title}")
        cursor_ms += dur_ms
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    safe_title = re.sub(r"[^\w\-() ]", "_", book_title).strip()
    output_m4b = book_dir / f"{safe_title}.m4b"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(concat_mp3),
        "-i", str(meta_path),
        "-map_metadata", "1",
        "-map", "0:a",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_m4b)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    concat_list.unlink(missing_ok=True)
    concat_mp3.unlink(missing_ok=True)
    meta_path.unlink(missing_ok=True)
    return output_m4b

def parse_epub(file_path: Path):
    book = epub.read_epub(str(file_path))
    chapters = []
    idx = 1
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            clean_text = TextNormalizer.normalize(text)
            if len(clean_text) > 100:
                title = f"Bolum_{idx:03d}"
                h1 = soup.find('h1')
                if h1 and h1.text.strip():
                    slug = re.sub(r'\W+', '_', h1.text.strip())[:30]
                    title = f"Bolum_{idx:03d}_{slug}"
                chapters.append((title, clean_text))
                idx += 1
    return chapters

def parse_pdf(file_path: Path, max_chunk=4500):
    doc = fitz.open(str(file_path))
    raw_pages = [page.get_text() for page in doc]
    cleaned_pages = TextNormalizer.strip_running_headers(raw_pages)
    full_text = "\n\n".join(cleaned_pages)
    full_text = TextNormalizer.normalize(full_text)

    paragraphs = [p.strip() for p in re.split(r'\n{1,}', full_text) if p.strip()]
    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) + 1 > max_chunk and current:
            chunks.append(current.strip())
            current = p
        else:
            current = (current + " " + p).strip()
    if current:
        chunks.append(current.strip())
    return [(f"Parca_{i+1:03d}", c) for i, c in enumerate(chunks)]

def process_book_pipeline(filename: str):
    file_path = BOOKS_DIR / filename
    job_status[filename] = {"status": "processing", "progress": "Başlıyor..."}
    try:
        out_book_dir = AUDIO_DIR / file_path.stem
        out_book_dir.mkdir(parents=True, exist_ok=True)
        chapters = parse_epub(file_path) if file_path.suffix.lower() == '.epub' else parse_pdf(file_path)
        total = len(chapters)
        for i, (title, text) in enumerate(chapters):
            out_mp3 = out_book_dir / f"{title}.mp3"
            if not out_mp3.exists():
                synthesize_chapter(text, out_mp3)
            job_status[filename] = {"status": "processing", "progress": f"Bölüm {i+1}/{total} bitti"}
        job_status[filename] = {"status": "processing", "progress": "Sesli kitap (m4b) birleştiriliyor..."}
        m4b_path = build_audiobook(out_book_dir, file_path.stem)
        m4b_info = f" -> {m4b_path.name}" if m4b_path else ""
        job_status[filename] = {"status": "completed", "progress": f"Bitti! Klasör: {file_path.stem}{m4b_info}"}
    except Exception as e:
        job_status[filename] = {"status": "error", "progress": str(e)}

@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    file_path = BOOKS_DIR / file.filename
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    job_status[file.filename] = {"status": "queued", "progress": "Kuyruğa alındı..."}
    background_tasks.add_task(process_book_pipeline, file.filename)
    return {"filename": file.filename, "status": "queued"}

@app.get("/status")
def get_status():
    return job_status

@app.get("/library")
def get_library():
    books = []
    for book_dir in sorted(AUDIO_DIR.iterdir()):
        if not book_dir.is_dir():
            continue
        m4b_files = list(book_dir.glob("*.m4b"))
        if not m4b_files:
            continue
        enc_dir = quote(book_dir.name)
        books.append({
            "title": book_dir.name,
            "m4b": f"/audio-files/{enc_dir}/{quote(m4b_files[0].name)}"
        })
    return {"books": books}

CHUNK_SIZE = 1024 * 1024  # 1 MB

@app.get("/audio-files/{book_name}/{file_name}")
async def stream_audio(book_name: str, file_name: str, request: Request):
    file_path = AUDIO_DIR / book_name / file_name
    if not file_path.exists():
        raise HTTPException(404, "Dosya bulunamadı")

    file_size = file_path.stat().st_size
    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    range_header = request.headers.get("range")

    if range_header:
        try:
            range_value = range_header.strip().split("=")[1]
            start_str, end_str = range_value.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
        except (IndexError, ValueError):
            start, end = 0, file_size - 1
        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iterfile():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    read_size = min(CHUNK_SIZE, remaining)
                    data = f.read(read_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(chunk_size),
            "Content-Type": content_type,
        }
        return StreamingResponse(iterfile(), status_code=206, headers=headers)

    def iterfile_full():
        with open(file_path, "rb") as f:
            while True:
                data = f.read(CHUNK_SIZE)
                if not data:
                    break
                yield data

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
        "Content-Type": content_type,
    }
    return StreamingResponse(iterfile_full(), headers=headers)

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Dedplay Kitap Okuma</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }
            .container { max-width: 600px; margin: 0 auto; background: #1e293b; padding: 30px; border-radius: 12px; }
            h1 { color: #38bdf8; font-size: 20px; }
            .dropzone { border: 2px dashed #475569; padding: 40px; text-align: center; border-radius: 8px; cursor: pointer; background: #0f172a; }
            input[type="file"] { display: none; }
            button { background: #0284c7; color: white; border: none; padding: 12px; border-radius: 6px; width: 100%; margin-top: 15px; font-weight: bold; cursor: pointer; }
            button:hover { background: #0369a1; }
            .status-list { margin-top: 25px; border-top: 1px solid #334155; padding-top: 15px; font-size: 13px; }
            .job-item { background: #0f172a; padding: 10px; border-radius: 6px; margin-bottom: 6px; display: flex; justify-content: space-between; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📚 Dedplay Kitap Okuma</h1>
            <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
                <p id="fileLabel">EPUB/PDF sürükle veya tıkla seç</p>
                <input type="file" id="fileInput" accept=".epub,.pdf" onchange="fileSelected()">
            </div>
            <button onclick="uploadFile()">Dönüşümü Başlat</button>
            <div class="status-list" id="statusList">Aktif işlem yok</div>

            <h2 style="color:#38bdf8; font-size:16px; margin-top:30px;">📖 Tamamlanan Kitaplar</h2>
            <div id="libraryList" style="margin-top:10px;"></div>
        </div>
        <script>
            let selectedFile = null;
            const dropzone = document.getElementById('dropzone');
            const fileInput = document.getElementById('fileInput');
            dropzone.addEventListener('dragover', (e) => { e.preventDefault(); });
            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                if (e.dataTransfer.files.length > 0) { fileInput.files = e.dataTransfer.files; fileSelected(); }
            });
            function fileSelected() {
                if (fileInput.files.length > 0) {
                    selectedFile = fileInput.files[0];
                    document.getElementById('fileLabel').innerText = "Seçilen: " + selectedFile.name;
                }
            }
            async function uploadFile() {
                if(!selectedFile) return alert("Dosya seç!");
                const fd = new FormData(); fd.append('file', selectedFile);
                await fetch('/upload', { method: 'POST', body: fd });
                alert("Kuyruğa eklendi!");
            }
            async function pollStatus() {
                const res = await fetch('/status'); const data = await res.json();
                const list = document.getElementById('statusList');
                const keys = Object.keys(data);
                list.innerHTML = keys.length === 0 ? 'Aktif işlem yok' : keys.map(k => `<div class="job-item"><b>${k}</b><span>${data[k].progress}</span></div>`).join('');
            }
            setInterval(pollStatus, 3000); pollStatus();

            async function loadLibrary() {
                const res = await fetch('/library');
                const data = await res.json();
                const container = document.getElementById('libraryList');
                if (data.books.length === 0) {
                    container.innerHTML = '<p style="color:#94a3b8; font-size:13px;">Henüz tamamlanmış kitap yok.</p>';
                    return;
                }
                container.innerHTML = data.books.map(book => {
                    return `<div style="background:#0f172a; padding:12px; border-radius:8px; margin-bottom:10px;">
                        <b>${book.title}</b>
                        <audio controls preload="none" style="width:100%; margin-top:8px;"><source src="${book.m4b}" type="audio/mp4"></audio>
                    </div>`;
                }).join('');
            }
            loadLibrary();
        </script>
    </body>
    </html>
    """
