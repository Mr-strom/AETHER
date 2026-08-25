# AETHER v1.2 Offline Audio Evidence — Research Record

## Selected binding

The v1.2 Android audio-evidence workflow uses **whisper.rn 0.7.3**, a maintained React Native binding for whisper.cpp. Its repository describes local React Native support for Whisper and confirms Expo projects require a native prebuild. [1]

The official documentation states that transcription runs on-device, supports file transcription, and supports Whisper model sizes including **Base** and quantized variants. [2]

## Evidence contract

The official file-transcription documentation defines a result with text segments containing `t0` and `t1` in milliseconds. AETHER maps each returned segment to one local audio evidence chunk with `startMs` and `endMs`, retaining the original private WAV URI for replay. [3]

The same documentation requires WAV / raw PCM in **16 kHz, mono, 16-bit PCM** form for reliable file transcription. AETHER v1.2 deliberately accepts only WAV audio evidence rather than falsely implying support for arbitrary MP3/AAC recordings. [3]

## Privacy and resource boundaries

AETHER never downloads an ASR model at runtime. The user selects a local Whisper Base GGML `.bin` file once; the app copies it to private storage, initializes it only during transcription, then releases the context. It uses two CPU threads and does not show invented RAM values.

## References

[1]: https://github.com/mybigday/whisper.rn
[2]: https://mybigday-whisper-rn.mintlify.app/introduction
[3]: https://mybigday-whisper-rn.mintlify.app/features/transcription
