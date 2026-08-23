# 🛍️ AliExpress AI Product Hunter

A full-stack, containerized web application that searches AliExpress for any product, scrapes real-time listings with Playwright stealth evasions, strictly evaluates arbitrary user-defined criteria using the **Google Gemini API**, stores structured search records in a persistent **SQLite database**, and allows interactive **manual CAPTCHA resolution** directly from the web browser.

---

## 🌟 Key Features

1. **Arbitrary Search Terms & Custom Criteria**:
   - Search for any category (e.g. *Gaming Headsets*, *Mechanical Keyboards*, *TWS Earbuds*, *Smart Watches*, etc.).
   - Define any number of strict conditions in natural language (e.g. *"Must have hardware ANC, rotary knob, 2.4GHz USB dongle, under $80 AUD, ships to Australia"*).

2. **Gemini AI Structured Evaluation**:
   - Uses the official `google-genai` SDK (`gemini-2.5-flash` / `gemini-3.7-flash`).
   - Breaks down user conditions into granular checks and rigorously determines if each item meets all requirements with cited evidence from specs and product page data.
   - Users provide their own Gemini API key in the UI (stored securely in browser `localStorage`).

3. **Interactive In-Browser CAPTCHA Solver**:
   - If AliExpress automated evasion triggers a verification challenge (`punish` slide-to-verify), the backend streams a live viewport screenshot directly into an interactive frontend modal.
   - Users can drag the slider inside the web browser canvas to resolve the challenge, immediately resuming the scraping pipeline.

4. **Persistent SQLite Database & History**:
   - Every search is saved with its metadata, candidate listings, AI verdict reasons, condition-by-condition breakdown, and specs.
   - Dedicated **Saved Searches** tab with quick search recall, detailed product cards, and instant deletion from the database.

5. **Docker Container Ready**:
   - Single-command container deployment with Playwright Chromium and shared memory pre-configured.

---

## 🚀 Quick Start

### Method 1: Running with Docker (Recommended)

```bash
# Build and run the container with Docker Compose
docker compose up --build
```

Open your browser and navigate to: **`http://localhost:8000`**

---

### Method 2: Running Locally with Python

1. **Activate virtual environment & install requirements**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Start the FastAPI web server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Access the Web UI**:
   Open **`http://localhost:8000`** in your browser.

---

## 🔑 Setting up your Gemini API Key

1. Click the **"Set Gemini API Key"** button in the top right header of the web app.
2. Enter your Google Gemini API Key (obtained from [Google AI Studio](https://aistudio.google.com/)).
3. Click **"Validate & Save"**. The app tests the key against the Gemini API and saves it locally in your browser storage.

---

## 📂 Project Architecture

```
├── app/
│   ├── main.py            # FastAPI REST & SSE endpoints
│   ├── scraper.py         # Playwright stealth scraping & live CAPTCHA streaming
│   ├── ai_evaluator.py    # Gemini API condition evaluation & keyword generator
│   ├── database.py        # Async SQLite database engine (aiosqlite)
│   ├── models.py          # Pydantic data schemas
│   └── static/
│       ├── index.html     # Modern SPA web interface (Tailwind CSS)
│       ├── app.js         # Reactive client logic & interactive CAPTCHA solver
│       └── styles.css     # Custom UI styling
├── data/
│   └── searches.db        # Persistent SQLite database file
├── Dockerfile             # Container definition with Playwright
├── docker-compose.yml     # Docker Compose orchestration
└── requirements.txt       # Python dependencies
```
