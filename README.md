# IELTS Listening Audio Generation Pipeline

Turns structured JSON test scripts into finished, multi-speaker IELTS
Listening test MP3s using the ElevenLabs API.

```
JSON test scripts
    -> parser.py            (per-speaker turns, delivery tags, 30s silence markers)
    -> tts_client.py         (ElevenLabs API, one voice per speaker, cached per line)
    -> audio_pipeline.py     (true 30s silence, ambience bed, Section 1-4 merge via ffmpeg/pydub)
    -> output/<TestID>.mp3
```

---

## 1. Prerequisites

| Requirement | Why | Check |
|---|---|---|
| Python 3.10+ | Runs the pipeline | `python --version` |
| FFmpeg | pydub shells out to it for all audio processing | `ffmpeg -version` |
| An ElevenLabs account + API key | Text-to-speech | https://elevenlabs.io |

### Install FFmpeg (Windows)

```powershell
winget install --id Gyan.FFmpeg -e
```

Close and reopen PowerShell afterward, then confirm:

```powershell
ffmpeg -version
```

If `ffmpeg -version` doesn't work after installing, FFmpeg's `bin` folder
isn't on your PATH — add it manually via *System Properties → Environment
Variables → Path*, then open a new terminal.

---

## 2. Get the project onto your machine

Put all the project files (`main.py`, `parser.py`, `tts_client.py`,
`audio_pipeline.py`, `config.py`, `requirements.txt`, etc.) into one
folder, e.g. `E:\Listening_test`.

---

## 3. Create and activate a virtual environment

```powershell
cd E:\Listening_test

python -m venv venv

.\venv\Scripts\Activate.ps1
```

Your prompt should now show `(venv)` at the start of the line.

**If activation fails** with *"running scripts is disabled on this
system"*, allow script execution for your user once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then re-run `.\venv\Scripts\Activate.ps1`.

---

## 4. Install requirements

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` contains:

```
requests>=2.31          # HTTP calls to the ElevenLabs API
pydub>=0.25.1             # audio assembly (concatenation, silence, ambience, export)
python-dotenv>=1.0        # loads your .env file automatically
audioop-lts; python_version >= "3.13"   # pydub dependency removed from stdlib in Python 3.13+
```

### After installation — verify it worked

```powershell
python -c "import requests, pydub, dotenv; print('OK')"
```

Should print `OK` with no errors. If you're on Python 3.13+ and see
`ModuleNotFoundError: No module named 'audioop'` later when running the
pipeline, it means `audioop-lts` didn't install — run
`pip install audioop-lts` directly.

---

## 5. Set your ElevenLabs API key

Never hardcode the key in `config.py`. Use a local `.env` file instead
(it's git-ignored, so it's never committed or shared):

```powershell
Copy-Item .env.example .env
notepad .env
```

Edit the file so it reads:

```
ELEVENLABS_API_KEY=your-real-key-here
ELEVENLABS_MODEL_ID=eleven_v3
```

Save and close. `config.py` loads this automatically via `python-dotenv`
every time you run the pipeline — no need to re-enter it per session.

> ⚠️ If you ever paste your key into a chat, terminal log, or anywhere
> public, treat it as compromised and revoke/regenerate it immediately
> from your ElevenLabs dashboard (Profile → API Keys).

---

## 6. Configure voices per speaker

Open `config.py` and edit `VOICE_POOL`. Every speaker name that appears
in your JSON scripts (`Emily`, `Daniel`, `Guide`, `Mark`, `Nina`,
`Professor Bennett`, etc.) needs a real ElevenLabs `voice_id`:

```python
"Emily": {"voice_id": "REPLACE_WITH_REAL_VOICE_ID", "accent": "en-GB", "desc": "Female, warm, British"},
```

Find voice IDs in the ElevenLabs Voice Library (elevenlabs.io → Voices →
click a voice → copy its ID). Pick accents matching British / Australian
/ American / Canadian as appropriate per speaker.

The placeholder IDs shipped in `config.py` are generic sample voices —
replace them before a real run, or you may get the wrong accent or a
"voice not found" error if an ID doesn't exist in your account.

---

## 7. Add your test data

Put your test JSON file at `data\tests.json` (or anywhere — you'll pass
the path with `--input`). Expected shape:

```json
{
  "tests": {
    "TEST01": {
      "testId": "TEST01",
      "title": "MOCK TEST 1",
      "sections": {
        "section1": { "sectionNumber": 1, "script": "..." },
        "section2": { "sectionNumber": 2, "script": "..." },
        "section3": { "sectionNumber": 3, "script": "..." },
        "section4": { "sectionNumber": 4, "script": "..." }
      },
      "sourceNotes": "..."
    }
  }
}
```

---

## 8. Run the pipeline

```powershell
# Build specific tests
python main.py --input data\tests.json --tests TEST01 TEST02

# Build every test found in the JSON
python main.py --input data\tests.json --all
```

You should see per-section parse counts, then a final MP3 path, e.g.:

```
Pipeline mode: LIVE (eleven_v3)

=== Building TEST01: MOCK TEST 1 ===
  Section 1: 5 audio segments, 43 turns
  Section 2: 5 audio segments, 25 turns
  Section 3: 5 audio segments, 43 turns
  Section 4: 3 audio segments, 36 turns
  -> output\TEST01.mp3 (16525 KB)
```

Output lands in `output\TEST01.mp3`, `output\TEST02.mp3`, etc.

### If it's interrupted or a request fails

Every synthesized line is cached in `cache\` (keyed on voice + tag +
text). Network errors and rate limits (HTTP 429) now auto-retry with
backoff; if a test still fails, the pipeline logs it and moves on to the
next test instead of aborting the whole run. Just re-run the same
command — completed lines are skipped, so it resumes quickly instead of
re-synthesizing (and re-billing) everything from scratch.

---

## 9. Deactivate the venv when done

```powershell
deactivate
```

Next time, you only need to `cd` into the project and re-activate:

```powershell
cd E:\Listening_test
.\venv\Scripts\Activate.ps1
python main.py --input data\tests.json --all
```
(no need to reinstall requirements or re-enter the API key each time)

---

## Project files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point — orchestrates parse → synthesize → assemble → export |
| `config.py` | API key/model (via `.env`), speaker→voice_id map, timing/ambience constants |
| `parser.py` | Raw script text → structured per-speaker turns, tags, silence markers |
| `tts_client.py` | ElevenLabs REST calls, per-line disk cache, retry/backoff on network errors |
| `audio_pipeline.py` | Builds each section (turns→clips→gaps→silence→ambience), merges Section 1–4 |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for your local `.env` (copy to `.env`, fill in your key) |
| `.gitignore` | Keeps `.env`, `cache/`, `output/`, `venv/` out of version control |
| `data/` | Put your test JSON here |
| `output/` | Final generated MP3s land here |
| `cache/` | Per-line synthesized audio cache (safe to delete to force re-synthesis) |

---

## MOCK mode (no API key / testing without spending credits)

If `ELEVENLABS_API_KEY` is not set (no `.env`, or an empty value), the
pipeline runs in **MOCK mode**: it generates placeholder audio (a faint
low hum, timed to roughly match how long each line would take to speak)
instead of calling the API. This lets you validate parsing, timing,
silence placement, and section merging for free before running for real.
You'll see `Pipeline mode: MOCK (no ELEVENLABS_API_KEY set)` printed at
the start of the run.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ffmpeg` not found / pydub export errors | Install FFmpeg (`winget install --id Gyan.FFmpeg -e`), reopen PowerShell |
| `Activate.ps1 cannot be loaded because running scripts is disabled` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` |
| `ModuleNotFoundError: No module named 'audioop'` (Python 3.13+) | `pip install audioop-lts` |
| `FileNotFoundError: data\tests.json` | Check the path with `dir data`; pass the correct path via `--input` |
| `ElevenLabs API error 401` | Invalid/missing API key — check `.env` |
| `ElevenLabs API error 404 ... voice` | The `voice_id` in `config.py` doesn't exist in your account — replace with a real one from your Voice Library |
| `ConnectionResetError` / network errors mid-run | Now auto-retried with backoff; if it still fails, just re-run the same command — cached lines are skipped |
| Pipeline runs but produces only faint hums | You're in MOCK mode — `ELEVENLABS_API_KEY` isn't being picked up. Check `.env` exists and is filled in |
| `pip install` fails behind a proxy | Add `--proxy http://user:pass@host:port` to the `pip install` command |
