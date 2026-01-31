from flask import Flask, request, send_file, render_template_string, abort
import os, uuid, time
import requests

app = Flask(__name__)

# ==== SETTINGS (boleh ubah) ====
MAX_MB = 50  # batas ukuran file (biar aman untuk publik)
ALLOWED_EXT = {"mp4", "jpg", "jpeg", "png", "pdf"}
DOWNLOAD_DIR = "downloads"
# ===============================

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Simple File Downloader</title>
  <style>
    body{font-family:Arial;max-width:780px;margin:40px auto;padding:0 16px}
    input{width:100%;padding:12px;font-size:16px}
    button{padding:12px 16px;font-size:16px;margin-top:10px}
    .hint{color:#666;margin-top:10px}
    .box{border:1px solid #ddd;border-radius:12px;padding:18px}
  </style>
</head>
<body>
  <h2>Simple File Downloader</h2>
  <div class="box">
    <form method="post" action="/download">
      <input name="url" placeholder="Paste direct file URL (mp4/jpg/png/pdf)" required>
      <button type="submit">Download</button>
    </form>
    <div class="hint">
      Max size: {{max_mb}}MB • Allowed: mp4/jpg/jpeg/png/pdf<br/>
      Tips: kalau link kamu bukan direct file, biasanya tidak bisa.
    </div>
  </div>
</body>
</html>
"""

def guess_ext(url: str) -> str:
    base = url.split("?")[0].split("#")[0]
    name = base.split("/")[-1]
    if "." in name:
        ext = name.rsplit(".", 1)[-1].lower()
        return ext
    return ""

def cleanup_old_files(seconds: int = 3600):
    # hapus file lebih dari 1 jam (biar folder gak numpuk)
    now = time.time()
    for fn in os.listdir(DOWNLOAD_DIR):
        path = os.path.join(DOWNLOAD_DIR, fn)
        try:
            if os.path.isfile(path) and now - os.path.getmtime(path) > seconds:
                os.remove(path)
        except:
            pass

@app.get("/")
def home():
    cleanup_old_files()
    return render_template_string(HTML, max_mb=MAX_MB)

@app.post("/download")
def download():
    cleanup_old_files()

    url = request.form.get("url", "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        abort(400, "URL harus http/https")

    ext = guess_ext(url)
    if ext not in ALLOWED_EXT:
        abort(400, f"Extension tidak diizinkan. Allowed: {', '.join(sorted(ALLOWED_EXT))}")

    # cek ukuran via HEAD (kalau server support)
    try:
        h = requests.head(url, allow_redirects=True, timeout=15)
        size = h.headers.get("Content-Length")
        if size and int(size) > MAX_MB * 1024 * 1024:
            abort(413, f"File terlalu besar. Max {MAX_MB}MB")
    except:
        pass  # kalau HEAD gagal, lanjut download tapi tetap dibatasi saat streaming

    out_name = f"dl_{uuid.uuid4().hex}.{ext}"
    out_path = os.path.join(DOWNLOAD_DIR, out_name)

    max_bytes = MAX_MB * 1024 * 1024
    downloaded = 0

    with requests.get(url, stream=True, allow_redirects=True, timeout=30) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    f.close()
                    try: os.remove(out_path)
                    except: pass
                    abort(413, f"File terlalu besar. Max {MAX_MB}MB")
                f.write(chunk)

    return send_file(out_path, as_attachment=True, download_name=out_name)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)