# Piper Voice Model Setup

Piper needs a local voice model (`.onnx` + `.onnx.json`).  
These files are **not** committed to the repository (they are large).

Recommended location:

```
voice_models/piper/
```

Default voice used by the project: `en_US-lessac-medium`

---

## Download (Windows – PowerShell)

```powershell
# Create the directory
mkdir voice_models\piper
cd voice_models\piper

# Download the .onnx model
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx" -OutFile "en_US-lessac-medium.onnx"

# Download the .json config
Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" -OutFile "en_US-lessac-medium.onnx.json"
```

---

## Download (macOS / Linux)

```bash
# Create the directory
mkdir -p voice_models/piper
cd voice_models/piper

# Download the .onnx model
curl -L -o en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx

# Download the .json config
curl -L -o en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

---

## Verify

After downloading you should see both files:

```
voice_models/piper/en_US-lessac-medium.onnx
voice_models/piper/en_US-lessac-medium.onnx.json
```

The application will look for the model at the path configured in `Settings.piper_voice_path` (default: `voice_models/piper/en_US-lessac-medium.onnx`).
