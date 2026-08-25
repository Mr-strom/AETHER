# AETHER Offline v1.2

AETHER is a privacy-first Android evidence assistant for **local text and timestamped WAV audio evidence**. It stores supported files on the device, retrieves evidence locally, shows citations and an answer trace, and can use an optional local GGUF model for grounded generation.

## What works in v1.2

| Capability | v1.2 behavior |
|---|---|
| Text evidence | Import TXT, MD, CSV, JSON, LOG, and RST files up to 12 MB. |
| Audio evidence | Import 16 kHz mono 16-bit PCM WAV recordings up to 120 MB, transcribe them locally with a user-supplied Whisper Base GGML model, and retrieve timestamped segments. |
| Evidence inspection | Every answer has citations, local retrieval reasons, original text/audio transcript excerpts, and an answer-pipeline trace. |
| Audio replay | An audio citation replays the exact cited local time range from the private WAV source. |
| Local model | A user-supplied GGUF model can provide grounded local generation after citation validation. |
| Online explanation | Disabled by default. When enabled, it sends only the selected citation excerpt and question to the configured explanation service. |

> **Privacy boundary:** AETHER does not download ASR or LLM models at runtime. Import your model packs manually. Audio transcription, text retrieval, local citations, and local model generation remain on-device.

## Requirements

| Tool | Recommended version |
|---|---:|
| Node.js | 22.x |
| pnpm | 9.x |
| Android SDK | API 35 or compatible installed SDK |
| Android NDK | 27.1.12297006 |
| JDK | 17 |

## Local development

```bash
pnpm install
pnpm check
pnpm lint
pnpm test
pnpm run dev
```

The browser preview supports text evidence and the interface, but Android-only capabilities—Whisper transcription, private WAV playback, and local native-model loading—must be tested in the installed APK.

## Build an Android APK

```bash
CI=1 npx expo prebuild --platform android --clean --no-install
cd android
JAVA_HOME=/path/to/jdk-17 ANDROID_HOME=/path/to/android-sdk ANDROID_SDK_ROOT=/path/to/android-sdk ./gradlew assembleRelease
```

The APK is created at:

```text
android/app/build/outputs/apk/release/app-release.apk
```

## Offline model setup

1. In **Settings**, select **Add local Whisper Base model** and choose a compatible local `ggml-base.bin` model.
2. In **Evidence vault**, select the waveform action and choose a 16 kHz mono 16-bit PCM `.wav` recording.
3. AETHER copies the recording into private storage, transcribes it locally, and indexes genuine `startMs` / `endMs` evidence segments.
4. Ask a question and tap an **Audio** citation to replay the referenced time range.

Whisper file transcription and timestamp segment behavior follow the maintained [whisper.rn](https://github.com/mybigday/whisper.rn) binding documentation. The v1.2 architecture record is in [`V12_AUDIO_ARCHITECTURE_RESEARCH.md`](./V12_AUDIO_ARCHITECTURE_RESEARCH.md).

## Explicit limitations

PDF, DOCX, images, camera OCR, arbitrary compressed audio formats, speaker diarization, and cross-modal embedding retrieval are **not** implemented in v1.2. The repository intentionally does not claim them as complete capabilities.

## Repository hygiene

This project ignores generated native folders, `node_modules`, build output, local environment files, and signing keys. Regenerate Android using Expo prebuild after cloning rather than committing generated build artifacts.

## Open source acknowledgement

Timestamped offline audio transcription is powered by [whisper.rn](https://github.com/mybigday/whisper.rn), a React Native binding for whisper.cpp. Please consider supporting the maintainers.
