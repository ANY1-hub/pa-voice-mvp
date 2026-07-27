export function playBase64Audio(b64) {
    if (!b64) return;
    try {
        // Piper usually returns raw PCM / wav-like data; browsers handle data-uri well
        const audio = new Audio("data:audio/wav;base64," + b64);
        audio.play().catch((err) => console.warn("Audio playback failed:", err));
    } catch (err) {
        console.warn("Could not create audio element:", err);
    }
}

export async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    const chunks = [];

    return new Promise((resolve, reject) => {
        recorder.ondataavailable = (e) => {
            if (e.data.size > 0) chunks.push(e.data);
        };

        recorder.onstop = () => {
            stream.getTracks().forEach((t) => t.stop());
            const blob = new Blob(chunks, { type: "audio/webm" });
            resolve(blob);
        };

        recorder.onerror = (e) => reject(e.error || new Error("Recording failed"));

        recorder.start();
        // Return a stop function so the caller can end the recording
        resolve({
            stop: () => recorder.stop(),
            _recorder: recorder, // internal
        });
    });
}
