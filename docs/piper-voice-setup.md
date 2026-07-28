# Piper Voice Model Setup

Piper needs local voice models (`.onnx` + `.onnx.json`) per language.  
These files are **not** committed to the repository (they are large).

Recommended location:

```
voice_models/piper/
```

## Supported languages (MVP)

| Code | Voice | File |
|------|--------|------|
| `en` | British English – Alan (medium) | `en_GB-alan-medium.onnx` |
| `de` | German – Thorsten (medium) | `de_DE-thorsten-medium.onnx` |
| `hu` | Hungarian – Anna (medium) | `hu_HU-anna-medium.onnx` |

At least **one** model must be present. Missing languages fall back to the
default loaded voice (preferring `en`).

Paths can be overridden via env / `.env`:

```env
PIPER_VOICE_EN=voice_models/piper/en_GB-alan-medium.onnx
PIPER_VOICE_DE=voice_models/piper/de_DE-thorsten-medium.onnx
PIPER_VOICE_HU=voice_models/piper/hu_HU-anna-medium.onnx
```

---

## Download (Windows – PowerShell)

```powershell
mkdir voice_models\piper
cd voice_models\piper

# British English
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx" -OutFile "en_GB-alan-medium.onnx"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json" -OutFile "en_GB-alan-medium.onnx.json"

# German
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx" -OutFile "de_DE-thorsten-medium.onnx"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json" -OutFile "de_DE-thorsten-medium.onnx.json"

# Hungarian
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx" -OutFile "hu_HU-anna-medium.onnx"
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx.json" -OutFile "hu_HU-anna-medium.onnx.json"
```

---

## Download (macOS / Linux)

```bash
mkdir -p voice_models/piper
cd voice_models/piper

# British English
curl -L -o en_GB-alan-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx
curl -L -o en_GB-alan-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json

# German
curl -L -o de_DE-thorsten-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx
curl -L -o de_DE-thorsten-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json

# Hungarian
curl -L -o hu_HU-anna-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx
curl -L -o hu_HU-anna-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/hu/hu_HU/anna/medium/hu_HU-anna-medium.onnx.json
```

---

## Verify

You should have pairs of files:

```
voice_models/piper/en_GB-alan-medium.onnx
voice_models/piper/en_GB-alan-medium.onnx.json
voice_models/piper/de_DE-thorsten-medium.onnx
voice_models/piper/de_DE-thorsten-medium.onnx.json
voice_models/piper/hu_HU-anna-medium.onnx
voice_models/piper/hu_HU-anna-medium.onnx.json
```

On startup the backend logs which voices were loaded.  
Language for TTS is chosen from STT hint + simple heuristics on the reply text.
