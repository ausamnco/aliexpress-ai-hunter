# 🛍️ AliExpress AI Product Hunter

A full-stack, containerized web application that searches AliExpress for any product, scrapes real-time listings with Playwright stealth evasions, strictly evaluates arbitrary user-defined criteria using the **Google Gemini API**, stores structured search records in a persistent **SQLite database**, and allows interactive **manual CAPTCHA resolution** directly from the web browser.

---

## 🚀 Running with Docker Compose (No repo clone required)

You can run the pre-built image directly on any computer with Docker without cloning the full repository.

### 1. Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  aliexpress-ai-hunter:
    image: ghcr.io/ausamnco/aliexpress-ai-hunter:latest
    container_name: aliexpress-ai-hunter
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./aliexpress-ai-hunter/data:/data
    environment:
      - PYTHONUNBUFFERED=1
      - DB_PATH=/data/searches.db
    shm_size: '2gb'
```

### 2. Start the container:

```bash
docker compose up -d
```

### 3. Open the Web UI:
Navigate to **`http://localhost:8000`** *(or `http://<server-ip>:8000`)* in your web browser.

---

## 🔑 Setting up your Gemini API Key

1. Click the **"Set Gemini API Key"** button in the top right header of the web app.
2. Enter your Google Gemini API Key (obtained from [Google AI Studio](https://aistudio.google.com/)).
3. Click **"Validate & Save"**. The app tests the key against the Gemini API and saves it locally in your browser storage.

---

## 🌟 Key Features

1. **Arbitrary Search Terms & Custom Criteria**:
   - Search for any category (e.g. *Gaming Headsets*, *Mechanical Keyboards*, *TWS Earbuds*, *Smart Watches*, etc.).
   - Define any number of strict conditions in natural language (e.g. *"Must have hardware ANC, rotary knob, 2.4GHz USB dongle, under $80 AUD, ships to Australia"*).

2. **Gemini AI Structured Evaluation**:
   - Uses the official `google-genai` SDK (`gemini-2.5-flash` / `gemini-3.7-flash`).
   - Breaks down user conditions into granular checks and rigorously determines if each item meets all requirements with cited evidence from specs and product page data.

3. **Interactive In-Browser CAPTCHA Solver**:
   - If AliExpress automated evasion triggers a verification challenge (`punish` slide-to-verify), the backend streams a live viewport screenshot directly into an interactive frontend modal.
   - Users can drag the slider inside the web browser canvas to resolve the challenge, immediately resuming the scraping pipeline.

4. **Persistent SQLite Database & History**:
   - Every search is saved with its metadata, candidate listings, AI verdict reasons, condition-by-condition breakdown, and specs.
   - Dedicated **Saved Searches** tab with quick search recall, detailed product cards, and instant deletion from the database.
