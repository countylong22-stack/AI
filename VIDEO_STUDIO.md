# Rooster Video Studio

Rooster Video Studio uses the OpenAI API to turn a video idea into a structured,
AI-video-ready production plan: consistent visual identity, scene prompts,
voiceover, on-screen text, sound design, and edit notes.

## Setup

Never put an API key in source code.

### Windows PowerShell

Set a session-only key:

```powershell
$env:OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
```

Or configure the key securely outside the repository. If using GitHub Actions,
store it as a repository secret named `OPENAI_API_KEY`.

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Make Joe's #45 Chrome GT3 video

From the repository root:

```powershell
python video_studio.py "Create a cinematic 2-minute GT3 night race starring car number 45, a chrome silver mirror-finish GT3. Start three-wide into Turn 1, include a near-spin and recovery, a comeback through traffic, a final-lap chase, a last-corner pass, and a photo-finish victory. Keep the exact same car design, number 45, lighting style, and realistic motorsport physics throughout." --seconds 120 --format vertical
```

The generated plan is saved to:

`video_projects/rooster_video_plan.json`

## Architecture

OpenAI handles the creative planning layer. The resulting scene prompts are
designed to be passed to a video-generation provider and then assembled into
the final MP4.

This separation is intentional: the Rooster project should not hard-code a
single video vendor. A future provider adapter can consume the same scene-plan
JSON and render each scene.

## Security

- `OPENAI_API_KEY` is read from the environment.
- Never commit the key to Git.
- Do not put keys in `.py` files, README files, screenshots, or GitHub Actions YAML.
