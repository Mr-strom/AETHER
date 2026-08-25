# AETHER Offline Regression Matrix

| Flow | Expected result |
|---|---|
| First launch | The privacy boundary, text-source limits, local Whisper Base setup, timestamped WAV evidence scope, and evidence-pipeline scope are shown; the app opens only after acknowledgement. |
| Valid TXT/MD/CSV/JSON/LOG/RST import | The file is copied into private storage, indexed, and a visible success notice gives the chunk count. |
| Unsupported PDF/DOCX/image/text import | The text importer remains open and shows a precise unsupported-format message. |
| Empty, oversized, duplicate, or unreadable file | The app remains open, removes incomplete private copies, and shows a recovery message. |
| Grounded chat | A local answer includes only selected EID citations and an Answer Trace. |
| Unsupported question | The app returns `INSUFFICIENT_EVIDENCE` with an abstention reason. |
| Model file | An invalid or oversized model shows an error notice; a compatible local GGUF enables local generation. |
| Whisper Base model | Android accepts a user-supplied compatible multilingual `ggml-base.bin` / Base GGML model, copies it privately, loads it only while transcribing, then releases it. No ASR model is fetched over the network. |
| WAV audio evidence on Android | A 16 kHz mono 16-bit PCM WAV is copied into private storage, transcribed locally into genuine `startMs` / `endMs` evidence segments, and becomes retrievable alongside text. Physical-phone model and WAV validation remains required. |
| WAV audio evidence in browser preview | The user sees a clear Android-only message; the preview does not attempt cloud, WASM, or native transcription. |
| Audio citation playback | An Android audio citation seeks to its cited start time and pauses after its cited end time. Browser preview describes this boundary without attempting native playback. |
| Resource bar | Browser preview reports native RAM unavailable without numeric placeholders. Android states that Whisper and the LLM are released between tasks instead of inventing RAM usage. |
| Evidence Pipeline | Every answer trace displays query validation, retrieval, evidence selection, citation validation, and optional generation/fallback or abstention stage. |
| Clear workspace | Local source copies, evidence, messages, and persisted runtime state are removed while acknowledgement and the separately installed Whisper model remain available. |
| Online Explain disabled | Citation drill-down shows matched terms and the exact local chunk only; no network explanation request is made. |
| Online Explain enabled | After the user explicitly enables the setting and taps Explain online, only the selected snippet and question are sent to the managed LLM service for a grounded plain-language explanation. |
| Network or service unavailable | The citation sheet keeps the local chunk visible and shows an error; it does not invent an online explanation or block offline evidence inspection. |
| Online APK permissions | The opt-in online-explain release declares INTERNET and ACCESS_NETWORK_STATE. The v1.2 audit confirms microphone, biometric, storage, and background-playback permissions are removed. |
| Array-shaped LLM content | Explanation parsing joins text parts returned by a managed model instead of incorrectly reporting an empty response. |
| Production UI refresh | Chat, citation detail, answer trace, sources, settings, and navigation use the minimal production visual system without changing the underlying local-evidence behavior. |
| Preview watcher stability | Generated Android build artifacts are excluded from Metro watching; preview and API listeners restart cleanly after a release build. |
| v1.2 WAV boundary | The audio-evidence importer accepts only 16 kHz mono 16-bit PCM WAV input up to 120 MB; MP3/AAC and browser audio ingestion are rejected with recovery guidance. |
| v1.2 package | TypeScript, lint, 14 deterministic tests, browser export, and a signed arm64 Android APK build complete successfully. |
