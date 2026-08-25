# AETHER Mobile Product Design — Production Refresh

## Product direction

**AETHER** is a private evidence assistant, not a dashboard. The redesign uses a quiet, reading-first conversation surface inspired by the clarity of modern assistant products without copying any specific product’s interface. The default experience answers from local evidence; online explanation is a clearly separated, per-citation enhancement.

The product must feel credible in an official demonstration: information is calm, the source of every answer is inspectable, and every potentially networked action is explicit. The target is portrait Android use, with primary actions placed in the lower thumb zone and no reliance on hover, hidden desktop controls, or decorative metric clutter.

## Screen list

| Screen | Primary content and function |
|---|---|
| Chat | A quiet conversation feed, concise assistant answers, cited evidence chips, a fixed composer, and a compact workspace status instead of a permanent telemetry dashboard. |
| Evidence detail | A focused sheet for one citation: source location, a plain local selection reason, timestamped WAV replay when relevant, a single optional online explanation control, a clear request/result/error state, and the exact local excerpt. |
| Answer trace | A readable, chronological explanation of retrieval and validation. Summary values precede an expandable-looking event timeline. |
| Sources | A clean evidence library with separate text and WAV import actions, source state, size, evidence-segment count, and safe deletion. |
| Settings | Everyday privacy and assistant controls first; local GGUF and Whisper Base model setup grouped under advanced device tools. |
| Onboarding | A brief privacy boundary: local by default, optional online explanation requires a deliberate user action. |

## Core flows

```text
Ask question
  → retrieve local evidence
  → present grounded answer + compact citations
  → tap citation
  → read local selection reason + exact excerpt
  → optional: tap Explain in plain language
  → show a privacy-bound online explanation OR preserve the local-only fallback
```

```text
Online explanation unavailable
  → show “Couldn’t generate an online explanation”
  → keep the local reason and exact excerpt visible
  → offer retry only
  → never replace evidence with a fabricated answer
```

```text
Import 16 kHz mono WAV
  → copy recording into private app storage
  → load local Whisper Base only for transcription
  → create real timestamped transcript evidence segments
  → release Whisper context
  → tap audio citation to replay only its cited time range
```

## Layout and interaction

The Chat header contains an AETHER wordmark, a one-line local workspace state, and an understated privacy indicator. A slim workspace summary replaces the three-column RAM strip; advanced telemetry remains available from Settings. Assistant replies are unboxed or lightly surfaced, while user messages retain stronger contrast. Evidence chips use human-readable labels such as **Source 1** or **Audio 1** rather than large opaque IDs. The lower composer exposes a low-emphasis text-import action and a distinct waveform action for private WAV evidence; there is no microphone-command flow.

The evidence sheet is the main explainability surface. It opens at a comfortable reading height, uses a short title and source subtitle, and places plain-language selection context before the original excerpt. An audio citation adds one warm, compact playback row that seeks to its actual timestamp range and then pauses; it never claims to replay an invented time range. The optional online feature appears as a small secondary action, not a large colored card. It labels exactly what is shared before the user invokes it. Online output appears in a neutral explanation card with a model-service label; errors use a brief retry row rather than a large red paragraph.

Every interactive control has a 44 px or larger target. The composer remains fixed above the safe area. Import, voice, and send actions have distinct low-emphasis icon buttons, with send becoming primary only when a valid question is present. Motion remains limited to 120–220 ms fades and press feedback.

## Visual system

| Token | Value | Purpose |
|---|---:|---|
| Ink | `#182230` | Primary text, navigation, and trusted contrast. |
| Paper | `#FCFCFA` | Warm neutral application background. |
| Surface | `#FFFFFF` | Sheets, composer, and document cards. |
| Line | `#E7E7E3` | Quiet borders and separators. |
| Muted | `#6F7480` | Secondary text and metadata. |
| Indigo | `#5B5BD6` | Focused primary action and active navigation. |
| Moss | `#2F7B68` | Local, verified, and ready status. |
| Sand | `#F4F0E8` | Soft low-emphasis information backgrounds. |
| Alert | `#B4534A` | Recoverable error and abstention state. |

Typography uses an editorial hierarchy: 28 px screen titles, 18 px response titles, 15–16 px body content, and 12 px metadata. Labels use sentence case, not all-caps technical headings. Spacing is intentionally generous: 16 px page gutters, 12–16 px component gaps, and 20–24 px separation between content groups.

## Explainability standard

The app must always distinguish **local fact**, **local retrieval reason**, and **optional model explanation**. A model explanation is not evidence; the cited excerpt remains the source of truth. The interface never uses opaque internal IDs as the main title, never claims an online explanation was created when parsing fails, and never hides the original local excerpt after a network error.
