# 🤖 VICTOR: Premium AI Tactical Assistant

VICTOR is a state-of-the-art, voice-enabled, vision-capable AI tactical assistant designed to automate system, browser, and OS-level operations through natural language. Utilizing high-performance Large Language Models (LLMs) and Vision Language Models (VLMs) via key-rotated API endpoints, VICTOR provides seamless automation, web search, real-time research synthesis, and high-fidelity text-to-speech feedback.

---

## 🌟 Key Features

### 🧠 1. Cognitive Router & Execution Planner
- **Intent Classification**: Evaluates user queries and routes them to four primary pipelines: `chat`, `research`, `vision`, or `task`.
- **Plan Decomposition**: Intelligently splits multi-task instructions (e.g., *"Open notepad, set volume to 50%, and check the weather in Berlin"*) into sequential execution lists.
- **Memory Memorization**: Dynamically records user preferences, titles, names, and customized details into a local database (e.g., *"remember that my favorite color is crimson"*).
- **Multi-Session Context Stitching**: Scans all active and historical chat session files (ordered by modification time) to assemble a rolling history of the last 10 interactions for unified contextual awareness.

### 🖥️ 2. OS & Window Control
- **Volume & Brightness**: Seamlessly increases, decreases, mutes/unmutes, or sets system volume and brightness to exact percentages.
- **Window Management**: Minimizes, maximizes, toggles full screen, shows desktop, closes windows or specific applications, and cycles active programs.
- **Smart System Launchers**: Normalizes and opens over 20 preconfigured applications (Chrome, Brave, VS Code, Telegram, WhatsApp, Spotify, Settings, etc.) using system executables, protocol URIs, or PyAutoGUI keystroke fallbacks.
- **Power Utilities**: Handles system lock, screen display sleep, system reboot, and system shutdown commands.
- **Wi-Fi & Theme Toggles**: Toggles Wi-Fi adapters and switches between Windows Light and Dark system themes.
- **Keystroke & Clipboard Simulation**: Translates requests for basic editing tasks (Select All, Copy, Cut, Paste, Undo, Redo, Save, Enter, Escape) into simulated key events.

### 📂 3. Desktop Management
- **Desktop Organizing**: Automatically categorizes files on the Windows Desktop into designated folders (`Images`, `Documents`, `Videos`, `Music`, `Archives`, `Code`, `Executables`, `Others`) based on file extension while preserving `.lnk` and `.url` shortcuts.
- **Desktop Cleaning**: Safely archives clutter by moving non-link desktop files into a dated archive directory (`Desktop Archive YYYY-MM-DD`).
- **Desktop Stats & Listing**: Inspects and lists all files/folders on the desktop and computes the total disk space occupied.
- **Wallpaper Engine**: Updates the Windows desktop background using a local path or a web image URL (with automatic conversion of `.webp`/`.png` to `.bmp` via PIL).

### ⏰ 4. Native OS Scheduler & Reminders
- **Native Task Scheduling**: Schedules one-time events or custom alerts using the native Windows Task Scheduler (`schtasks`) from natural language queries (e.g., *"remind me to call John in 15 minutes"*).
- **System Notification Alerts**: Triggers a system beep audio cue (`winsound`) and a native Windows message alert box (`MessageBoxW`) when scheduled tasks are fired.

### 🌐 5. Web Browser & Media Automation
- **Direct Navigation**: Opens custom websites, handles domain aliases, and performs web actions.
- **Tab & Navigation Controls**: Controls tabs (new tab, close tab, next tab, previous tab), page history (back/forward), refresh, zoom controls, and page scrolling.
- **YouTube Playback Automation**: Resolves direct URLs or searches and plays YouTube content directly, bypassing standard search results.

### 🔍 6. Real-Time Web Research & Data Verification
- **Web Search**: Integrates Tavily API for fast, reliable search query execution.
- **Dual-Distillation**: Performs a single LLM request to generate a concise, 25-word summary (ideal for Text-To-Speech) and a detailed 150-word markdown sidebar breakdown with comparative tables and citation links.
- **Data & Currency Accuracy Engine**: Cross-references query results to reject outdated estimates (e.g., stale currency exchange rates) in favor of authoritative live values, ensuring strict data consistency without hallucination.

### 👁️ 7. Computer Vision
- **Image Analysis**: Uses Groq-powered Vision Language Models to analyze uploaded images or webcam snapshots.
- **Prompt Interaction**: Ask questions directly about the image (e.g. *"What do you see?"*, *"What color is this?"*).

### 🎙️ 8. High-Fidelity Voice Output (TTS)
- **Scrubbing Engine**: Cleans LLM outputs of thinking blocks (`<think>...</think>`), tables, markdown symbols, and emojis before synthesis.
- **Real-Time Streaming**: Uses `edge-tts` to stream audio bytes directly to the frontend.

### 📁 9. File Understanding & Reading Engine
- **Text & Code Files**: Parses plain text, Python, JavaScript, HTML, CSS, JSON, etc.
- **Office & Document Formats**: Extracts text from Word documents (`.docx`), Excel spreadsheets (`.xlsx`/`.xls`), and PDF documents (`.pdf`) using pre-installed document parsers (supporting fallbacks like `fitz`/`pypdf`).
- **Context Injection**: Intelligently appends extracted file contents (up to a 100k character limit to prevent token overflow) to the user prompt context, enabling the Cognitive Router and AI completion streams to seamlessly explain, summarize, or analyze files.
- **Auto-Chat Routing**: Detects file uploads and routes them directly to chat mode instead of misclassifying them as research queries.

---

## 📁 Project Structure

```
VICTOR/
├── run.py                 # Core startup script with validation checks
├── config.py              # Central configuration loader and folder setup
├── requirements.txt       # Project python dependencies
├── .env                   # API keys and system environment variables
├── app/
│   ├── main.py            # FastAPI main router, stream and upload endpoints
│   ├── models.py          # Pydantic data schemas
│   ├── services/
│   │   ├── ai_service.py        # LLM streaming & structured responses
│   │   ├── brain_service.py     # Cognitive routing & intent classification
│   │   ├── realtime_service.py  # Web search integration (Tavily)
│   │   ├── memory_service.py    # Session logs and persistent database
│   │   ├── vision_service.py    # VLM image analyzer
│   │   └── task_executor.py     # Windows & browser automation execution engine
│   └── utils/
│       ├── key_rotation.py      # API key rotating logic
│       ├── retry.py             # Error-handling & retry wrappers
│       └── time_info.py         # Timestamp helpers
├── database/              # Stores local persistent data
└── frontend/              # Sleek dark-mode dashboard files
```

---

## 🚀 Setup & Installation

### 1. Prerequisites
- **OS**: Windows 10/11
- **Python**: version 3.10 or 3.11
- **Dependencies**: Install required packages via pip:
  ```bash
  pip install -r requirements.txt
  ```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
PORT=8000
HOST=127.0.0.1

# Key Rotation Arrays (Up to 3 keys supported)
GROQ_API_KEY1=your-groq-key-1
GROQ_API_KEY2=your-groq-key-2
GROQ_API_KEY3=your-groq-key-3

TAVILY_API_KEY=your-tavily-key-1
TAVILY_API_KEY_2=your-tavily-key-2
TAVILY_API_KEY_3=your-tavily-key-3

GROQ_VLM_API_KEY_1=your-vlm-key-1
GROQ_VLM_API_KEY_2=your-vlm-key-2
GROQ_VLM_API_KEY_3=your-vlm-key-3

# Models
GROQ_MODEL=llama-3.1-8b-instant
GROQ_VLM_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

# TTS voice (e.g. en-GB-RyanNeural, en-US-ChristopherNeural)
TTS_VOICE=en-GB-RyanNeural
TTS_RATE=+22%

# Assistant Details
ASSISTANT_NAME=VICTOR
VICTOR_USER_TITLE=Sir
VICTOR_OWNER_NAME=Shashank
```

### 3. Launching VICTOR
Run the core startup script:
```bash
python run.py
```
This runs the initial system checks. If all variables are set, the FastAPI server will boot up and the premium dashboard will be hosted at `http://127.0.0.1:8000`.

---

## 🧪 Verified Feature Tests

VICTOR features have been thoroughly verified with a local programmatic test suite testing each service components end-to-end. Here are the results:

### 1. Cognitive Router & Planning
- Input: `"increase volume to 80%"` → Intent: `task`, Plan: `['Increase system volume to 80%']`
- Input: `"what's the weather in Paris?"` → Intent: `research`, Plan: `['Search for Paris weather']`
- Input: `"remind me to call John at 2026-06-15 14:30"` → Intent: `task`, Plan: `["Memorize key 'user_reminder' with value 'Call John at 2026-06-15 14:30'"]`
- Input: `"open youtube and play lo-fi music"` → Intent: `task`, Plan: `['Open YouTube and search for lo-fi music']`

### 2. Automation Step Translation
- Input: `"show weather in Paris"` → Primitive Action: `{'action': 'weather_report', 'city': 'Paris'}`
- Input: `"play lo-fi music on youtube"` → Primitive Action: `{'action': 'play_youtube', 'param': 'lo-fi'}`
- Input: `"open github.com"` → Primitive Action: `{'action': 'open_url', 'param': 'https://github.com'}`

### 3. AI Completion & Web Search
- **AI Completion Stream**: Successfully returns text-generation segments dynamically.
- **Tavily Web Search**: Successfully crawls, returns top relevance results, and maps URLs.

### 4. Text-To-Speech
- **Synthesize Speech**: Generates high-quality base64 audio chunks streaming cleanly to client browsers.

### 5. Vision Service (VLM)
- **VLM Response**: A 10x10 solid red PNG image was analyzed, returning:
  > *"The image is red."*

### 6. File Extraction & Understanding
- **Plain Text / Code Files**: Extracted functions and declarations successfully.
- **Word Documents (.docx)**: Successfully read test paragraphs from docx structures.
- **Excel Spreadsheet Data**: Extracted tables, names, and custom headers.
- **PDF Documents**: Read layout text streams from generated PDF pages successfully.

---

## 🛡️ License
Designed for personal use and automation assistance. All rights reserved to developer team.
