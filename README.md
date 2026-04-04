# VerseListener 🎙⛪

**Real-time speech-to-text with automatic Bible verse detection and EasyWorship integration.**

Built for church AV operators: listen to a sermon in real time, instantly detect any Bible verse reference spoken aloud, and send it directly to EasyWorship with one click (or a hotkey).

---

## Features

- 🎙 **Real-time audio capture** via JACK (primary) or sounddevice (fallback)
- 〰️ **Live audio waveform monitor** so you can verify the mic is flowing before text appears
- 🧠 **Speech-to-text backends** using OpenAI Realtime, faster-whisper, or Vosk
- 📖 **Bible verse detection** – all 66 books, dozens of abbreviations, natural-language patterns
  - `"Genesis 5:2"`, `"Gen 5 v 2"`, `"chapter 8 verse 28"`, `"Romans 8:28 through 30"`
- ⭐ **Verse queue** with timestamps, confidence scores, and editable references
- 🪟 **Local verse preview card** above the queue, powered by offline canon files in `canons/<EDITION>/verses.json`
- ⛪ **EasyWorship automation** via PyAutoGUI – clicks the search box, types the reference, presses Enter
- 🌗 **Dark and light themes**, church-friendly design
- ⌨ **Hotkey**: `Ctrl+Shift+S` sends the top queued verse to EasyWorship

---

## Requirements

- Python 3.10 or newer
- Linux (JACK/ALSA/PulseAudio) – primary platform
- Windows/macOS: supported via sounddevice + PyAutoGUI (JACK not required)

---

## Installation

### 1 – Clone / download the project

```bash
git clone https://github.com/anclatechs/verse-listener.git
cd verse-listener
```

### 2 – Create a virtual environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3 – Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3.1 – Configure `.env`

The project includes a ready-to-edit `.env` file.

Set at least:

```bash
OPENAI_API_KEY=your_key_here
VERSE_LISTENER_STT_BACKEND=openai_realtime
```

### 3.2 – Add local Bible preview text

For the queue preview card, place canon files like this:

```text
canons/
└── KJV/
    └── verses.json
```

The file should map references to verse text, for example:

```json
{
  "John 3:16": "For God so loved the world...",
  "John 3:17": "For God sent not his Son..."
}
```

### 4 – (Linux) Install system packages

```bash
sudo apt install python3-xlib wmctrl jackd2 qjackctl libportaudio2 portaudio19-dev
```

Optional Python backends for Linux window focus:

```bash
pip install PyWinCtl python-xlib
```

### 5 – (Optional) Download a Vosk model

If you prefer Vosk over faster-whisper:

```bash
mkdir -p ~/.vosk
cd ~/.vosk
# Download model from https://alphacephei.com/vosk/models
# Example: English small model
wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
unzip vosk-model-small-en-us-0.15.zip
mv vosk-model-small-en-us-0.15 model-en-us
```

---

## JACK Setup (Linux)

Start JACK with QJackCtl or via command line:

```bash
jackd -d alsa -r 44100 &
```

Or use QJackCtl (GUI) to configure and start JACK.

VerseListener will auto-connect to the first available physical capture port.  
You can also set the exact JACK port name in **Settings → Audio**.

If JACK is not running, VerseListener automatically falls back to sounddevice (PulseAudio/ALSA).

---

## Running the app

```bash
python main.py
```

## Recommended Speech-to-Text Setup

For this project, the best default setup is:

- Audio backend: `sounddevice` on Windows, `auto` or `jack` on Linux
- STT backend: `openai_realtime`
- OpenAI model: `gpt-4o-transcribe`

Why this is the best starting point:

- you get streaming partial transcripts instead of waiting on local chunked inference
- the `.env` prompt can bias the model toward Bible book names and verse notation
- you avoid CPU-heavy local Whisper inference

If you need a fully offline fallback:

- use backend `whisper` with model `small.en` or `base.en`

## OpenAI Realtime Setup

The app reads these values from `.env`:

```bash
OPENAI_API_KEY=your_key_here
VERSE_LISTENER_STT_BACKEND=openai_realtime
OPENAI_REALTIME_TRANSCRIBE_MODEL=gpt-4o-transcribe
OPENAI_REALTIME_LANGUAGE=en
OPENAI_REALTIME_PROMPT=...
```

Notes:

- `OPENAI_API_KEY` is required for the OpenAI backend
- `OPENAI_REALTIME_PROMPT` is a good place to bias scripture names, sermon terms, and punctuation style
- OpenAI Realtime transcription expects 24 kHz PCM; the app handles resampling before streaming audio

## Verse Preview

The right-hand queue panel includes a compact preview card above the detected verses list.

- Click a queued verse to load its text from `canons/<EDITION>/verses.json`
- Range references like `Romans 8:28-30` are combined into one preview
- Chapter-only references show the first few verses as a compact preview
- In **Settings → Interface**, you can adjust:
  - preview canon edition
  - preview max height
  - gradient start and end colors

### Optional: choose the EasyWorship window backend

VerseListener reads `VERSE_LISTENER_EW_WINDOW_BACKEND` at startup.

```bash
export VERSE_LISTENER_EW_WINDOW_BACKEND=auto
python main.py
```

Supported values:

- `auto` → Linux tries `pywinctl`, then `wmctrl`, then `xlib`, then `pygetwindow`
- `pywinctl`
- `wmctrl`
- `xlib`
- `pygetwindow`

Examples:

```bash
export VERSE_LISTENER_EW_WINDOW_BACKEND=pywinctl
export VERSE_LISTENER_EW_WINDOW_BACKEND=xlib
```

---

## EasyWorship Setup

1. Open EasyWorship on the same machine.
2. Click **"Calibrate EW"** in the VerseListener toolbar.
3. You have 3 seconds to move your mouse cursor to the **Bible search field** in EasyWorship.
4. VerseListener saves those coordinates.
5. From now on, clicking "Send to EasyWorship" will:
   - Focus the EasyWorship window
   - Click the search field
   - Type the verse reference (e.g. `Romans 8:28`)
   - Press Enter

### Adjusting timing

If EasyWorship is slow to respond, open **Settings → EasyWorship** and increase the delay values.

---

## Keyboard Shortcuts

| Shortcut       | Action                               |
| -------------- | ------------------------------------ |
| `Ctrl+R`       | Start / stop listening               |
| `Ctrl+Shift+S` | Send top queued verse to EasyWorship |

---

## Supported Verse Formats

VerseListener detects all of these (and more):

```
Genesis 5:2
Gen 5:2
Genesis chapter 5 verse 2
Gen ch 5 v 2
Romans 8:28-30
book of Romans chapter 8 verses 28 through 30
Psalm 23
1 Corinthians 13:4
First Corinthians 13:4
```

Full list of supported books and abbreviations: see `core/bible_detector.py`.

---

## Project Structure

```
verse_listener/
├── main.py                  # Entry point
├── requirements.txt
├── README.md
├── core/
│   ├── bible_detector.py    # Verse pattern matching
│   ├── bible_preview.py     # Local canon loading for verse preview
│   ├── transcription.py     # Audio capture + STT threads
│   ├── easyworship.py       # PyAutoGUI EasyWorship controller
│   └── settings.py          # Persistent settings
└── ui/
    ├── main_window.py       # Main application window
    ├── transcript_panel.py  # Live transcription display
    ├── queue_panel.py       # Detected verses queue
    ├── settings_dialog.py   # Settings UI
    └── styles.py            # Dark/light QSS stylesheets
```

---

## Troubleshooting

| Problem                                        | Solution                                                                         |
| ---------------------------------------------- | -------------------------------------------------------------------------------- |
| No audio captured                              | Check JACK is running; or set backend to `sounddevice` in Settings               |
| OpenAI realtime does not start                 | Check `OPENAI_API_KEY` in `.env` and confirm `websocket-client` is installed     |
| `PortAudio library not found`                  | Install `libportaudio2` (and, if needed, `portaudio19-dev`) then restart the app |
| Model takes long to load                       | First run downloads faster-whisper model; subsequent runs are fast               |
| EasyWorship not focused                        | Re-run calibration; increase Focus Delay in Settings                             |
| Verse preview is blank                         | Check that the selected edition exists under `canons/<EDITION>/verses.json`      |
| `PyGetWindow currently does not support Linux` | Set `VERSE_LISTENER_EW_WINDOW_BACKEND=pywinctl`, `wmctrl`, or `xlib`             |
| PyAutoGUI fails on Linux                       | Install `python3-xlib`: `sudo apt install python3-xlib`                          |
| JACK auto-connect fails                        | Manually connect ports in QJackCtl                                               |

---

## License

MIT – free to use and modify for church ministry purposes.
