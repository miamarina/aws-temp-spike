# Saved test data

[Back to the report](../README.md)

**The real input and results are saved here.** This archive is a retained part of the report and will survive temporary-file and AWS cleanup.

The AWS test resources were deleted on **8 November 2026**. These local files remain available; S3 locations in the manifest record their historical origins. [Cleanup receipt](../aws-cleanup.json)

## Open these first

| What you want | Local file |
| --- | --- |
| The exact 55-second cloud input | [Input video](input/vectors-study-55s.mp4) |
| The cloud-generated study guide: three bullets | [Study notes](cloud/mp4-01/bullets.md) |
| The cloud-generated timestamped transcript | [Transcript](cloud/mp4-01/transcript.md) |
| The WAV extracted inside Lambda | [Extracted audio](cloud/wav-01/fixture.wav) |
| The earlier local test’s study notes, with attribution | [Local study notes](local/study-notes.md) |

The clip is **00:00–00:55 of 3Blue1Brown’s Vectors lesson**. Keep its [source and attribution](ATTRIBUTION.md) with the data.

## What each folder holds

~~~text
spike-report/
  README.md                       report entry point
  01-local.md … 04-code.md         walkthroughs and tested code
  data/
    input/                        tested MP4 and original fixture metadata
    local/                        local ASR/LLM JSON, Markdown, and timings
    cloud/
      mp4-01/                     direct-MP4 run: transcript, bullets, raw JSON, timings
      wav-01/                     FFmpeg run: WAV, transcript, reused bullets, raw ASR, timings
    usage/
      groq-usage.json              snapshot of the complete campaign ledger
      cloud-attempts/              three S3 attempt-marker records
    manifest.json                 origins, sizes, and SHA-256 checksums
    ATTRIBUTION.md                 creator, source, and clip permission basis
~~~

## Inspect the raw cloud results

| Evidence | Direct MP4 run | FFmpeg/WAV run |
| --- | --- | --- |
| ASR response | [asr.json](cloud/mp4-01/asr.json) | [asr.json](cloud/wav-01/asr.json) |
| LLM response and tokens | [llm.json](cloud/mp4-01/llm.json) | Earlier bullets reused; zero extra LLM calls |
| Runtime and timings | [metadata.json](cloud/mp4-01/metadata.json) | [metadata.json](cloud/wav-01/metadata.json) |
| Saved transcript | [transcript.md](cloud/mp4-01/transcript.md) | [transcript.md](cloud/wav-01/transcript.md) |
| Saved bullets | [bullets.md](cloud/mp4-01/bullets.md) | [bullets.md](cloud/wav-01/bullets.md) |

The generated files are preserved without editing. The cloud bullets include an unsupported elaboration; the [report explains that quality limitation](../README.md#what-we-learned).

## What was checked

On **8 November 2026 (Vienna time)**, we preserved **23 data artifacts, 3,058,202 bytes total**: 14 S3 objects and 9 local evidence files.

- Downloaded S3 content matched its recorded size and single-upload ETag/MD5.
- The MP4’s SHA-256 matched the exact input used in the cloud tests.
- The WAV is 16 kHz, mono, 16-bit PCM, exactly 55 seconds.
- Both cloud transcripts match; both saved bullet files match.
- JSON parsing and credential-pattern checks passed.

The [manifest](manifest.json) records each artifact’s path, source, size, and SHA-256. No signed download URLs or API keys are saved in this archive.

`input/fixture-metadata.json` is the original preparation record, including its historical temporary path. Use the input-video link above for the retained copy.

The [usage snapshot](usage/groq-usage.json) records **165 submitted audio seconds and 2 LLM calls**. Archiving made no inference calls. The current campaign has 435 seconds and 1 LLM call unused; all planned inference is finished.
