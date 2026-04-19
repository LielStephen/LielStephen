"""
app.py — Flask web interface for the Face Authenticator.

Routes
------
  GET  /                  → index page
  POST /register          → register a face (multipart form: username, image file)
  POST /authenticate      → authenticate a face (multipart form: image file)
  GET  /users             → JSON list of registered users
  DELETE /users/<username>→ remove a user

Run
---
  python app.py
  # or
  flask --app app run --debug
"""

import os
import uuid
import logging
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

from face_auth import FaceAuthenticator

logging.basicConfig(format="[%(levelname)s] %(message)s", level=logging.INFO)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

_DB_DIR = Path(__file__).parent / "known_faces"
_UPLOAD_DIR = Path(__file__).parent / "tmp_uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)

auth = FaceAuthenticator(db_dir=_DB_DIR)


def _save_upload(file_storage) -> Path | None:
    """
    Validate that the upload is a real image (via PIL magic-byte check),
    then persist it as a JPEG in the temp directory.

    The output path is derived entirely from a UUID — the user-supplied
    filename is never used as part of the filesystem path.
    """
    try:
        from PIL import Image as _Image
        img = _Image.open(file_storage.stream)
        img.verify()  # raises if not a valid image
        # verify() exhausts the stream; re-open from the saved bytes
        file_storage.stream.seek(0)
        img = _Image.open(file_storage.stream)
        rgb = img.convert("RGB")
    except Exception:
        return None

    dest = _UPLOAD_DIR / f"{uuid.uuid4().hex}.jpg"
    rgb.save(dest, "JPEG")
    return dest


# ---------------------------------------------------------------------------
# HTML templates (inline — no extra files needed)
# ---------------------------------------------------------------------------

_INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Face Authenticator</title>
  <style>
    *{box-sizing:border-box;font-family:system-ui,sans-serif}
    body{max-width:760px;margin:40px auto;padding:0 20px;background:#0d1117;color:#e6edf3}
    h1{color:#58a6ff}h2{color:#79c0ff;margin-top:2rem}
    form{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:20px;margin-bottom:1.5rem}
    label{display:block;margin-bottom:6px;font-weight:600}
    input[type=text],input[type=file]{width:100%;padding:8px;background:#0d1117;
      border:1px solid #30363d;border-radius:6px;color:#e6edf3;margin-bottom:12px}
    button{background:#238636;color:#fff;border:none;padding:10px 20px;border-radius:6px;
      cursor:pointer;font-size:1rem}
    button:hover{background:#2ea043}
    .result{padding:12px;border-radius:6px;margin-top:10px}
    .ok{background:#0d2e1a;border:1px solid #238636;color:#56d364}
    .err{background:#2d0f0f;border:1px solid #f85149;color:#ffa198}
    ul{list-style:none;padding:0}li{padding:4px 0;border-bottom:1px solid #30363d}
    a{color:#58a6ff}
  </style>
</head>
<body>
  <h1>🔐 Face Authenticator</h1>

  {% if message %}
  <div class="result {{ 'ok' if success else 'err' }}">{{ message }}</div>
  {% endif %}

  <h2>Register a Face</h2>
  <form method="POST" action="/register" enctype="multipart/form-data">
    <label for="reg_user">Username</label>
    <input id="reg_user" name="username" type="text" placeholder="e.g. alice" required/>
    <label for="reg_img">Face Image</label>
    <input id="reg_img" name="image" type="file" accept="image/*" required/>
    <button type="submit">Register</button>
  </form>

  <h2>Authenticate a Face</h2>
  <form method="POST" action="/authenticate" enctype="multipart/form-data">
    <label for="auth_img">Face Image</label>
    <input id="auth_img" name="image" type="file" accept="image/*" required/>
    <button type="submit">Authenticate</button>
  </form>

  <h2>Registered Users</h2>
  <ul>
    {% for u in users %}
    <li>👤 {{ u }}
      <form method="POST" action="/users/{{ u }}/delete" style="display:inline;margin-left:10px">
        <button style="background:#b62324;padding:3px 10px;font-size:.85rem">Delete</button>
      </form>
    </li>
    {% else %}
    <li><em>No users registered yet.</em></li>
    {% endfor %}
  </ul>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    message = request.args.get("message")
    success = request.args.get("success", "true").lower() == "true"
    return render_template_string(_INDEX_HTML, users=auth.list_users(), message=message, success=success)


@app.route("/register", methods=["POST"])
def register():
    username = request.form.get("username", "").strip()
    file = request.files.get("image")

    if not username:
        return redirect(url_for("index", message="Username is required.", success=False))
    if not file or not file.filename:
        return redirect(url_for("index", message="Please upload a face image.", success=False))

    tmp_path = _save_upload(file)
    if tmp_path is None:
        return redirect(url_for("index", message="Unsupported image format.", success=False))

    try:
        result = auth.register(username, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return redirect(url_for("index", message=result["message"], success=result["success"]))


@app.route("/authenticate", methods=["POST"])
def authenticate():
    file = request.files.get("image")
    if not file or not file.filename:
        return redirect(url_for("index", message="Please upload a face image.", success=False))

    tmp_path = _save_upload(file)
    if tmp_path is None:
        return redirect(url_for("index", message="Unsupported image format.", success=False))

    try:
        result = auth.authenticate(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    if result["authenticated"]:
        msg = f"✅ Authenticated as '{result['username']}' (confidence: {result['confidence']:.2%})"
        return redirect(url_for("index", message=msg, success=True))

    return redirect(url_for("index", message=f"🚫 {result['message']}", success=False))


@app.route("/users", methods=["GET"])
def list_users():
    return jsonify({"users": auth.list_users()})


@app.route("/users/<username>/delete", methods=["POST"])
def delete_user(username: str):
    deleted = auth.delete_user(username)
    msg = f"User '{username}' removed." if deleted else f"User '{username}' not found."
    return redirect(url_for("index", message=msg, success=deleted))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
