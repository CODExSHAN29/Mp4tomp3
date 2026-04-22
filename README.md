# Minimal FastAPI File Conversion App

## Project Structure

```text
.
├── app/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       └── home.py
├── static/
│   └── .gitkeep
├── templates/
│   └── index.html
├── uploads/
│   └── .gitkeep
├── outputs/
│   └── .gitkeep
├── main.py
└── requirements.txt
```

## Run Locally

1. Create and activate a virtual environment (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the server:

```bash
uvicorn main:app --reload
```

4. Make sure FFmpeg is installed and available in your PATH.

5. Open:
- http://127.0.0.1:8000/
