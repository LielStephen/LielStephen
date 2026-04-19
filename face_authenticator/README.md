# 🔐 Face Authenticator

A biometric face authentication system built with Python.  
Register a user's face once; authenticate any future photo against the stored profile in milliseconds.

---

## Features

| Feature | Details |
|---------|---------|
| Face registration | Encodes a face from any photo and stores the 128-d embedding |
| Face authentication | Compares a probe image against all registered embeddings |
| Multiple enrollments | Register multiple photos per user for better accuracy |
| Duplicate guard | Prevents registering the same face twice for the same user |
| CLI + Web UI | Use it from the terminal **or** as a Flask web app |

---

## Tech Stack

- [`face_recognition`](https://github.com/ageitgey/face_recognition) — dlib-powered 128-d face embeddings
- `NumPy` — distance computations
- `Flask` — web interface
- `Pillow` — image loading helpers

---

## Installation

```bash
cd face_authenticator
pip install -r requirements.txt
```

> **Note:** `face_recognition` requires `dlib`. On Linux/macOS it installs automatically.  
> On Windows you may need to install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/) first (select "Desktop development with C++" workload).

---

## CLI Usage

### Register a face
```bash
python main.py register --user alice --image /path/to/alice.jpg
```

### Authenticate a face
```bash
python main.py authenticate --image /path/to/photo.jpg
# ✅  Authenticated as 'alice' (confidence: 94.32%)
```

### List registered users
```bash
python main.py list
```

### Delete a user
```bash
python main.py delete --user alice
```

### Custom database directory & tolerance
```bash
python main.py --db /custom/db --tolerance 0.45 authenticate --image photo.jpg
```

---

## Web App Usage

```bash
python app.py
# or
flask --app app run --debug
```

Open **http://localhost:5000** in your browser.

The web UI provides:
- Upload an image to **register** a new user
- Upload an image to **authenticate** against all known users
- View and delete registered users

---

## How It Works

```
Image → face_recognition.face_encodings() → 128-d vector
                                                  │
                      ┌───────────────────────────┘
                      ▼
         known_faces/<username>.json  (stores encoding list)
                      │
                      ▼  (at auth time)
         face_distance(known_encodings, probe)
                      │
                      ▼
         distance < tolerance?  → MATCH (return username + confidence)
                                → NO MATCH
```

Each face is represented as a **128-dimensional embedding**.  
Authentication computes the Euclidean distance between the probe embedding and every stored embedding; the closest match below the tolerance threshold wins.

---

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `--db` | `known_faces/` | Directory where face data is stored |
| `--tolerance` | `0.50` | Match threshold (lower = stricter). Recommended range: 0.4 – 0.6 |

---

## Project Structure

```
face_authenticator/
├── face_auth.py      ← Core authentication engine
├── main.py           ← CLI entry-point
├── app.py            ← Flask web interface
├── requirements.txt
├── known_faces/      ← Auto-created; stores <username>.json files
└── README.md
```

---

## Security Notes

- Face embeddings are stored as plain JSON. For production, encrypt the database at rest.
- Always use HTTPS when deploying the Flask app publicly.
- Consider rate-limiting the `/authenticate` endpoint to prevent brute-force attacks.
- The default tolerance of **0.50** works well for most use cases; lower it to **0.40–0.45** for higher security.
