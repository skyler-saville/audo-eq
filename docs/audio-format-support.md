# Audio format support

This document summarizes the current ingest/output format behavior for both the CLI and API paths.

## Supported input containers/codecs

Validation is implemented in `src/audo_eq/ingest_validation.py` and codec I/O is handled via `src/audo_eq/infrastructure/pedalboard_codec.py`.

### Accepted containers

- `.wav`
- `.flac`
- `.mp3`

### Accepted API MIME types

- `audio/wav`
- `audio/x-wav`
- `audio/flac`
- `audio/mpeg`
- `audio/mp3`

### Codec/profile limits

- **WAV**
  - Container must include valid `fmt ` and `data` chunks.
  - Codec must be format code `1` (PCM) or `3` (IEEE float).
- **FLAC**
  - Requires a valid STREAMINFO metadata block.
- **MP3**
  - Requires a parseable MPEG frame header.
  - Only **MPEG-1 Layer III** is accepted.
  - Non-MPEG-1 Layer III profiles are rejected.

### Policy limits enforced at ingest

- Max size: `100 MiB`
- Max duration: `3600s` (1 hour)
- Sample rate: `8,000` to `192,000` Hz
- Channel count: `1` to `8`

## Output format and content-type behavior

- Mastered output bytes are returned as **WAV**.
- API responses are emitted with `Content-Type: audio/wav`.
- The object-storage persistence path uses the incoming target upload's `content_type` when present (fallback `audio/wav`), which may differ from the returned mastered media type.
- CLI output format is determined by the output filename/codec writer (`pedalboard.io.AudioFile`), but the service currently produces mastered audio in WAV form for API responses.

## Typical failures and user-facing error patterns

Validation errors return structured JSON as FastAPI `detail`, for example:

```json
{
  "detail": {
    "code": "unsupported_container",
    "message": "Unsupported or unrecognized audio container."
  }
}
```

### `415 Unsupported Media Type`

Returned only for ingest validation codes:

- `unsupported_container`
- `unsupported_codec`

Common examples:

- Unsupported extension, e.g. `target.txt`
- Unknown container signature in file bytes
- WAV format code outside PCM/IEEE-float

### `400 Bad Request`

Returned for all other ingest/validation/mastering payload failures, including:

- `empty_file`
- `file_too_large`
- `corrupted_file`
- `mp3_malformed_header`
- `id3_malformed_header`
- `unsupported_codec_profile`
- `invalid_duration`
- `duration_too_long`
- `invalid_sample_rate`
- `invalid_channel_count`
- `invalid_payload` (domain/value error during mastering)

## Recommended preprocessing for problematic sources

If source audio repeatedly fails ingest, normalize it before upload:

1. **Transcode into a known-good container/codec**
   - Prefer WAV PCM (16-bit or 24-bit) or FLAC.
   - Avoid uncommon WAV codecs and MP3 variants other than MPEG-1 Layer III.
2. **Resample into supported rate range**
   - Use a standard production rate such as `44.1kHz` or `48kHz`.
3. **Constrain channel layout**
   - Downmix unusual multichannel layouts to mono/stereo unless wider layouts are required.
4. **Strip/repair broken metadata**
   - Re-export files with malformed ID3/headers from a DAW/editor.
5. **Trim or split long files**
   - Keep each submitted asset below 1 hour and 100 MiB.

