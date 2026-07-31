# On This Day

**On This Day** turns a historical event that happened on a given calendar date into a short, narrated, vertical
video — the kind of "on this day in history" content you'd see on TikTok, YouTube Shorts, or Reels.

It combines an LLM-driven content pipeline (event research → script → storyboard → images → animation prompts →
narration → final video) with a **Gradio app** for reviewing and steering every step, plus a **CLI** for
batch-processing dates and rendering the final video automatically.

> **Status:** this is an actively evolving personal/research project, not a polished product. The image → video
> animation step currently produces animation *prompts* only; wiring those prompts up to a video model
> (e.g. [LTX-Video](https://github.com/Lightricks/LTX-Video)) is in progress.

## Origin story

I ran this pipeline daily from **2025-09-15 to 2025-11-29**, with a self-imposed constraint: produce one video
per day for **under $1 in API costs** and **under 10 minutes of manual steering** in the app (picking an event,
a hook, a storyboard, and the images — everything else automated via the CLI). The resulting videos are posted
on TikTok: [@on_this_day_videos](https://www.tiktok.com/@on_this_day_videos).

## How it works

The pipeline is organized as a sequence of stages, each with its own generated artifact saved to disk so you can
stop, inspect, and resume at any point:

```
Wikipedia "on this day"  →  Event research  →  Script          →  Storyboard
        events                & qualification    (hook + body)     (scenes + visual lookbook)
                                                                          │
                                                                          ▼
        Final video  ←  Narration + alignment  ←  Image prompts  ←  Storyboard scenes
      (MoviePy render)     (ElevenLabs TTS)         + generated images (Imagen)
```

1. **Event discovery** ([`src/scripts/wiki.py`](src/scripts/wiki.py)) — fetches every event that happened on a
   given month/day from Wikipedia's "on this day" pages, then uses Gemini to *qualify* each one against a set of
   editorial criteria (controversial events, firsts in history, crime & heists, revolutionary discoveries, etc.)
   and produce a short summary.
2. **Script generation** ([`src/scripts/scripts.py`](src/scripts/scripts.py)) — generates several candidate
   narration "hooks" for a chosen event, then a full narration script for whichever hook you pick.
3. **Text enhancement** ([`src/audio/text_enhancer.py`](src/audio/text_enhancer.py)) — enriches the script with
   ElevenLabs v3 audio tags (`[whispers]`, `[angry]`, etc.) for more expressive narration.
4. **Storyboarding** ([`src/image/storyboard_generator.py`](src/image/storyboard_generator.py)) — breaks the
   script into scenes, builds a "visual lookbook" of recurring characters/locations/objects for visual
   consistency, and derives an image prompt (+ negative prompt) per scene.
5. **Image generation** ([`src/image/imagen.py`](src/image/imagen.py)) — generates candidate images per scene
   with Google's Imagen (Vertex AI). Any one of several candidate images per scene can be picked in the app.
6. **Animation prompting** ([`app/animation_tab.py`](app/animation_tab.py)) — turns each chosen image + scene
   into an image-to-video animation prompt (see "Status" above for the current limitation here).
7. **Narration** ([`src/audio/elevenlabs_tts.py`](src/audio/elevenlabs_tts.py)) — synthesizes the enhanced
   script with ElevenLabs, trims/cuts silence, and force-aligns the audio back to the text for word-level
   timing.
8. **Video assembly** ([`src/video/moviepy_video.py`](src/video/moviepy_video.py)) — renders the final vertical
   video with MoviePy: Ken Burns-style zoom on each image/clip, a title card, and karaoke-style word-by-word
   subtitles synced to the narration.

Every artifact for a given date is written to `prd/<YYYY-MM-DD>/` (see
[`examples/sample-output/`](examples/sample-output) for what these files look like). The pipeline is idempotent —
re-running a step skips work that's already been done on disk.

## The app

```bash
uv run python -m app.main
```

launches a Gradio UI with one tab per pipeline stage — **Events → Scripts → Storyboards → Images → Animations** —
sharing a single date-scoped state. Pick a year/month/day at the top, and each tab lets you:

- Generate candidates (hooks, scripts, storyboards, image prompts, images) with an adjustable LLM temperature.
- Browse and compare multiple candidates per step (sliders for hook/script/storyboard/image index).
- Pick a winner and save it, which unlocks the next tab.
- Regenerate an individual image or prompt with feedback ("what's wrong with this image?"), add/delete/edit
  script segments, and re-pick images from a gallery of candidates.

This is meant for **human-in-the-loop curation** — the automation you'd use once you're happy with the results
of manual curation lives in the CLI below.

## The CLI

```bash
# Fetch and qualify Wikipedia events for every date in a range (used to pre-warm data before opening the app)
uv run python -m app.automation fetch-events --start-date=2025-09-18 --end-date=2025-09-25

# Given a date where you've already chosen a script + images in the app, generate narration,
# align it, and render the final video
uv run python -m app.automation build-from-app --date=2025-09-18

# Clean up temporary audio/alignment artifacts for a given date + segment, e.g. to force a re-generation
uv run python -m app.automation clean-audio-part --date=2025-09-18 --part-index=2
```

## Getting started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for dependency management
- A **Google Cloud project** with the Vertex AI API enabled, for Gemini (script/storyboard/event generation) and
  Imagen (image generation). You'll need credentials available to the environment — typically via
  `gcloud auth application-default login` — see the
  [Vertex AI / google-genai SDK docs](https://cloud.google.com/vertex-ai/generative-ai/docs/start/quickstarts/quickstart-multimodal).
- An **[ElevenLabs](https://elevenlabs.io/) API key**, for narration (text-to-speech + forced alignment).

### Installation

```bash
git clone <this-repo-url>
cd on-this-day
uv sync
```

### Configuration

Configuration is managed with [Dynaconf](https://www.dynaconf.com/) across two files (see
[`src/config.py`](src/config.py)):

- **`settings.toml`** — tracked in git, non-secret defaults (model names, video/subtitle styling, filenames,
  audio processing thresholds, etc.).
- **`.secrets.toml`** — gitignored, holds real API keys and your GCP project/location. Copy the template to get
  started:

  ```bash
  cp .secrets.toml.example .secrets.toml
  ```

  Then fill in:

  | Key | Where to get it |
  |---|---|
  | `gemini.PROJECT_ID` / `gcp.imagen.PROJECT_ID` | Your GCP project ID (Vertex AI must be enabled) |
  | `gemini.LOCATION_ID` / `gcp.imagen.LOCATION_ID` | A Vertex AI region that supports the models below |
  | `eleven_labs.API_KEY` | [ElevenLabs dashboard](https://elevenlabs.io/app/settings/api-keys) |

  `settings.toml` also lets you pick which Gemini model backs each stage (`GEMINI_SCRIPT_GENERATOR`,
  `GEMINI_STORYBOARD_GENERATOR`, `GEMINI_WIKI_EVENTS`, etc.), the ElevenLabs voice/model ID, and all video/
  subtitle styling (fonts, colors, zoom speed, subtitle positioning) — see the comments in that file.

  **Never commit `.secrets.toml`.** It's gitignored by default; keep it that way.

### Fonts

Two fonts used for titles/subtitles are bundled under [`fonts/`](fonts) — no extra setup needed unless you want
to swap them via `settings.toml`.

## Project structure

```
app/                  Gradio UI (one *_tab.py module per pipeline stage) + the automation CLI
src/
  scripts/            Wikipedia event fetching/qualification, script generation
  image/              Storyboard, visual lookbook, and image-prompt/image generation
  audio/              TTS, audio enhancement, silence trimming, forced alignment
  video/              MoviePy video assembly, subtitle/title rendering
  gemini.py           Thin wrapper around google-genai for structured-output Gemini calls + cost tracking
  schemas.py          Pydantic models shared across the pipeline
fonts/                Bundled fonts for titles and subtitles
examples/sample-output/  A trimmed example of the JSON artifacts produced for one date
prd/                  Generated, per-date working directories (gitignored, created at runtime)
```

## Notes on cost

Every generation step in the app calls a paid API (Gemini, Imagen, or ElevenLabs). `src/gemini.py` tracks token
usage and estimated Gemini cost across a session; `src/image/imagen.py` exposes a rough per-image cost estimate
for the configured Imagen model. There's no hard spending cap — keep an eye on your GCP/ElevenLabs billing,
especially while iterating on prompts.

## License

[MIT](LICENSE)
