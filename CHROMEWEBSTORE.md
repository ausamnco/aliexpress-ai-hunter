# Chrome Web Store Listing: AliExpress AI Product Hunter

## Store Listing Metadata

- **Extension Name**: AliExpress AI Product Hunter
- **Summary / Short Description**: Instant AI criteria verification and visual match filtering directly on AliExpress search results.
- **Detailed Description**:
  AliExpress AI Product Hunter helps you find the exact products you need on AliExpress by automatically analyzing product specifications and listings against your strict custom criteria using Google Gemini AI.

  ### Key Features:
  - **⚡ Instant 0-Lag DOM Extraction**: Reads and parses product listings directly from your active browser tab in under 100 milliseconds without requiring external scraping proxies.
  - **🧠 Intelligent Gemini AI Verification**: Evaluates complex criteria (e.g. "Active Noise Cancellation", "2.4GHz wireless dongle included", "Under $100 AUD") against product titles, descriptions, and technical specifications.
  - **🏷️ Visual Match Badges**: Directly annotates AliExpress product cards with clean visual badges (✓ MATCH or ✕ EXCLUDED) and hover tooltips explaining the exact reasoning for each criterion.
  - **🔍 Smart Floating Filter**: Easily filter the AliExpress search page to display only verified matches with a single click.

---

## Permissions Justification

| Permission | Justification |
| :--- | :--- |
| `storage` | Required to save the user's custom criteria, model selection, and API key locally on their browser. |
| `activeTab` | Required to extract product cards and inject visual match badges onto the active AliExpress page when the user clicks the analyze button. |
| `scripting` | Required to inject the content script into active AliExpress search tabs for on-page badge rendering. |

### Host Permissions Justification:
- `*://*.aliexpress.com/*` and `*://*.aliexpress.us/*`: Required to detect AliExpress product listings and render on-page match badges.
- `http://localhost:8000/*` and `http://127.0.0.1:8000/*`: Required to connect to the optional local AI Hunter Docker backend for ultra-fast batch evaluations.
- `https://generativelanguage.googleapis.com/*`: Required for direct Gemini AI specification verification when running standalone without the local Docker backend.

---

## Privacy & Data Handling Disclosure

- **Personal Data Collected**: None.
- **Data Transmission**: Product titles, prices, and user-provided criteria are sent directly to Google Gemini API (or the user's self-hosted local Docker container) for criteria verification. No data is sent to any third-party tracking or analytics servers.
- **Authentication**: API keys are stored strictly in `chrome.storage.local` on the user's machine.

---

## Developer Loading Instructions

To load the extension in Google Chrome, Brave, or Microsoft Edge:
1. Open your browser and navigate to `chrome://extensions`.
2. Toggle on **Developer mode** in the top-right corner.
3. Click **Load unpacked**.
4. Select the `extension` folder located in this repository (`/home/ausamnco/.gemini/antigravity/scratch/AliExpress Search/extension`).
5. Open any search page on `https://www.aliexpress.com`, click the AliExpress AI Hunter icon, and click **Analyze Current Page**!
