/**
 * Audio utilities for J.A.R.V.I.S. frontend.
 *
 * Responsibilities:
 * - Playback of base64 TTS audio from the backend
 * - Microphone recording via MediaRecorder
 * - Conversion of browser audio (typically webm/opus) to 16 kHz mono WAV
 *
 * Why WAV 16 kHz mono?
 * Whisper (faster-whisper) works reliably with this format.
 * Doing the conversion in the browser keeps the backend simple and
 * avoids native ffmpeg installs on end-user machines.
 */

/** Currently playing TTS element (if any). */
let currentTts = null;

/** Optional callbacks for speaking indicator. */
let onSpeakingStart = null;
let onSpeakingEnd = null;

/**
 * Register callbacks for TTS playback lifecycle.
 * @param {{ onStart?: () => void, onEnd?: () => void }} handlers
 */
export function setSpeakingHandlers({ onStart, onEnd } = {}) {
    onSpeakingStart = onStart || null;
    onSpeakingEnd = onEnd || null;
}

/**
 * Stop any currently playing TTS audio.
 */
export function stopTts() {
    if (currentTts) {
        currentTts.pause();
        currentTts.src = "";
        currentTts = null;
        if (onSpeakingEnd) onSpeakingEnd();
    }
}

/**
 * Play a base64-encoded WAV payload returned by the backend TTS.
 * @param {string|null|undefined} b64 - Base64 audio data (WAV)
 */
export function playBase64Audio(b64) {
    if (!b64) return;

    stopTts();

    try {
        const audio = new Audio("data:audio/wav;base64," + b64);
        currentTts = audio;

        const finish = () => {
            if (currentTts === audio) {
                currentTts = null;
                if (onSpeakingEnd) onSpeakingEnd();
            }
        };

        audio.addEventListener("ended", finish);
        audio.addEventListener("error", (e) => {
            console.warn("Audio playback error:", e);
            finish();
        });

        if (onSpeakingStart) onSpeakingStart();

        audio.play().catch((err) => {
            console.warn("Audio playback failed:", err);
            finish();
        });
    } catch (err) {
        console.warn("Could not create audio element:", err);
        if (onSpeakingEnd) onSpeakingEnd();
    }
}

/**
 * Start a microphone recording session.
 *
 * Usage (toggle pattern):
 *   const session = await startRecordingSession();
 *   // ... later, when user clicks stop:
 *   const wavBlob = await session.stop();
 *
 * @returns {Promise<{ stop: () => Promise<Blob> }>}
 *   stop() ends the recording, converts to 16 kHz mono WAV, and resolves with the Blob.
 */
export async function startRecordingSession() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Most browsers produce webm/opus; we convert afterwards.
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

    const recorder = new MediaRecorder(stream, { mimeType });
    const chunks = [];

    recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.start();

    /**
     * Stop recording and return a 16 kHz mono WAV Blob ready for Whisper.
     * @returns {Promise<Blob>}
     */
    function stop() {
        return new Promise((resolve, reject) => {
            recorder.onstop = async () => {
                // Release the microphone immediately
                stream.getTracks().forEach((t) => t.stop());

                try {
                    const rawBlob = new Blob(chunks, { type: mimeType });
                    const wavBlob = await convertToWav16kMono(rawBlob);
                    resolve(wavBlob);
                } catch (err) {
                    reject(err);
                }
            };

            recorder.onerror = (e) => {
                stream.getTracks().forEach((t) => t.stop());
                reject(e.error || new Error("Recording failed"));
            };

            recorder.stop();
        });
    }

    return { stop };
}

/**
 * Decode an arbitrary audio Blob and re-encode it as 16 kHz mono PCM WAV.
 * @param {Blob} blob - Input audio (webm, ogg, …)
 * @returns {Promise<Blob>} - audio/wav at 16 kHz mono
 */
async function convertToWav16kMono(blob) {
    const arrayBuffer = await blob.arrayBuffer();

    // Request 16 kHz so the browser resamples while decoding when possible
    const audioCtx = new AudioContext({ sampleRate: 16000 });
    let decoded;
    try {
        decoded = await audioCtx.decodeAudioData(arrayBuffer.slice(0));
    } finally {
        await audioCtx.close();
    }

    return encodeWav(decoded);
}

/**
 * Encode an AudioBuffer as a mono 16-bit PCM WAV Blob.
 * If the buffer has multiple channels they are mixed down to mono.
 * @param {AudioBuffer} buffer
 * @returns {Blob}
 */
function encodeWav(buffer) {
    const sampleRate = buffer.sampleRate;
    const samples = buffer.numberOfChannels > 1
        ? mixToMono(buffer)
        : buffer.getChannelData(0);

    const dataLength = samples.length * 2; // 16-bit
    const totalLength = 44 + dataLength;
    const arrayBuffer = new ArrayBuffer(totalLength);
    const view = new DataView(arrayBuffer);

    // RIFF header
    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + dataLength, true);
    writeString(view, 8, "WAVE");
    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);          // PCM chunk size
    view.setUint16(20, 1, true);           // PCM format
    view.setUint16(22, 1, true);           // mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true); // byte rate
    view.setUint16(32, 2, true);           // block align
    view.setUint16(34, 16, true);          // bits per sample
    writeString(view, 36, "data");
    view.setUint32(40, dataLength, true);

    // Samples
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }

    return new Blob([arrayBuffer], { type: "audio/wav" });
}

/** Mix multi-channel AudioBuffer down to a single Float32Array. */
function mixToMono(buffer) {
    const channels = [];
    for (let c = 0; c < buffer.numberOfChannels; c++) {
        channels.push(buffer.getChannelData(c));
    }
    const length = channels[0].length;
    const mono = new Float32Array(length);
    for (let i = 0; i < length; i++) {
        let sum = 0;
        for (let c = 0; c < channels.length; c++) sum += channels[c][i];
        mono[i] = sum / channels.length;
    }
    return mono;
}

function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}
