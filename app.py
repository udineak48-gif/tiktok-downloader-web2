from flask import Flask, request, send_file, render_template_string
import requests
from urllib.parse import urlparse
import io

app = Flask(__name__)

ALLOWED_EXT = {"mp4", "jpg", "jpeg", "png", "pdf"}
MAX_MB = 50

HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Simple File Downloader</title>
  <style>
    body{font-family:Arial; max-width:720px; margin:40px auto; padding:0 14px;}
    input{width:100%; padding:12px; font-size:16px;}
    button{padding:10px 18px; margin-top:10px; font-size:16px;}
    .box{border:1px solid #ddd; padding:18px; border-radius:10px;}
    .tip{color:#666; margin-top:10px;}
    .err{color:#b00020; margin-top:10px;}
  </style>
</head>
<body>
  <h2>Simple File Downloader</h2>
  <div class="box">
    <form method="POST">
      <input name="url" placeholder="Paste direct file URL atau link TikTok (vt.tiktok.com / tiktok.com)" required>
      <button type="submit">Download</button>
    </form>
    <div class="tip">
      Max size: 50MB • Allowed direct: mp4/jpg/jpeg/png/pdf<br>
      TikTok link akan otomatis dicari link MP4-nya dulu.
    </div>
    {% if error %}<div class="err"><b>Bad Request</b><br>{{ error }}</div>{% endif %}
  </div>
</body>
</html>
"""

def is_tiktok(url: str) -> bool:
    u = url.lower()
    return "tiktok.com" in u or "vt.tiktok.com" in u

def get_ext_from_url(url: str) -> str:
    path = urlparse(url).path
    if "." not in path:
        return ""
    return path.rsplit(".", 1)[-1].lower()

def tiktok_to_mp4(url: str) -> str:
    api = "https://tikwm.com/api/"
    r = requests.get(api, params={"url": url}, timeout=20)
    r.raise_for_status()
    data = r.json()

    if not data.get("data"):
        raise ValueError("Gagal ambil data TikTok (mungkin link salah / video private).")

    mp4 = data["data"].get("play") or data["data"].get("wmplay")
    if not mp4:
        raise ValueError("Tidak ketemu link mp4 dari TikTok.")
    return mp4

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "GET":
        return render_template_string(HTML, error=None)

    url = request.form.get("url", "").strip()
    if not url.startswith("http"):
        return render_template_string(HTML, error="URL harus diawali http/https.")

    try:
        if is_tiktok(url):
            url = tiktok_to_mp4(url)

        ext = get_ext_from_url(url)
        if ext not in ALLOWED_EXT:
            return render_template_string(
                HTML,
                error=f"Extension tidak diizinkan. Allowed: {', '.join(sorted(ALLOWED_EXT))}."
            )

        with requests.get(url, stream=True, timeout=30) as resp:
            resp.raise_for_status()

            cl = resp.headers.get("Content-Length")
            if cl and int(cl) > MAX_MB * 1024 * 1024:
                return render_template_string(HTML, error=f"File terlalu besar. Maks {MAX_MB}MB.")

            buf = io.BytesIO()
            size = 0
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_MB * 1024 * 1024:
                    return render_template_string(HTML, error=f"File terlalu besar. Maks {MAX_MB}MB.")
                buf.write(chunk)

        buf.seek(0)
        filename = f"download.{ext}"
        return send_file(buf, as_attachment=True, download_name=filename)

    except requests.exceptions.RequestException:
        return render_template_string(HTML, error="Gagal fetch link. Coba link lain / koneksi bermasalah.")
    except Exception as e:
        return render_template_string(HTML, error=str(e))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
