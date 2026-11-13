# From a video to study notes: what we proved

**Architecture:** [start with the AWS docs](docs/README.md) for the [implemented spike](docs/spike-architecture.md), the [planned full project](docs/aws-architecture-report.md), and [design reasons/open issues](docs/aws-considerations.md).

**Session:** 7–8 November 2026, Europe/Vienna. We crossed midnight during the cloud tests.

**Result:** a short video can travel through S3 → Lambda → Groq → saved study notes. FFmpeg also works inside Lambda. All planned inference tests passed within our limits.

## Open the actual files

- [Input video: the exact 55-second MP4](data/input/vectors-study-55s.mp4)
- [Cloud-generated study guide: three bullets](data/cloud/mp4-01/bullets.md)
- [Cloud-generated timestamped transcript](data/cloud/mp4-01/transcript.md)

The [saved-data index](data/README.md) also links the extracted WAV, local results, both cloud runs, raw JSON, timings, and usage records. All are retained beside this report, with checksums and source information.

## The experiment in one picture

~~~mermaid
flowchart LR
    A["55-second MP4"] --> B["S3: store the input"]
    B --> C["Lambda: run the Python code"]
    C --> D["Groq Whisper: speech → text"]
    D --> E["Groq LLM: text → 3 bullets"]
    E --> F["S3: save Markdown + raw JSON"]
    C -. "second test: extract WAV first" .-> G["FFmpeg in a Lambda layer"]
    G -.-> D
~~~

We started this manually. Uploading a file did **not** trigger Lambda.

## Read one part at a time

| You want to… | Open… |
| --- | --- |
| Understand the result | Stay on this page |
| Recreate setup, the clip, and local tests | [1 · Start on your laptop](01-local.md) |
| Move the working calls into AWS | [2 · Prove the cloud path](02-cloud.md) |
| Add FFmpeg, review costs, and clean up | [3 · Finish the experiment](03-ffmpeg-and-cleanup.md) |
| Copy the tested handler, policies, and packaging code | [Code appendix](04-code.md) |
| Browse the actual inputs, generated outputs, and checksums | [Saved test data](data/README.md) |

The walkthrough follows the work we did. Where an original command was not preserved, it gives a reconstruction recipe and labels it. We did not run another experiment just to write this report.

## What happened

| Test | Observed result |
| --- | --- |
| AWS access and Free Plan | Login/identity worked; application resources stayed in Stockholm, `eu-north-1` |
| Groq authentication | Model-list request: HTTP 200; both chosen models listed |
| Local MP4 → transcript | HTTP 200, 16 timestamped segments, **0.675 s** |
| Local transcript → bullets | HTTP 200, 3 useful bullets, **326 tokens** |
| Lambda → direct MP4 ASR → bullets → S3 | Passed; handler **1.271 s**, LLM **355 tokens** |
| Lambda → FFmpeg → WAV → ASR → S3 | Passed; handler **1.825 s**; same transcript; reused the bullets |

**How to read these timings:** they describe one small input. Handler time measures our code; Lambda also bills initialization and runtime overhead. These are not long-video performance guarantees.

## Why we tested in this order

First we removed uncertainty about access and quotas. Then we tested Groq locally, where failures are easier to inspect. Once that worked, we changed only the execution environment: the same clip and models moved into Lambda. Finally, we added FFmpeg as one extra dependency.

Each successful step gave the next step a known input. That is the point of this fail-fast spike: find expensive assumptions before building the full application.

## What we learned

**Use direct MP4 submission for the first short-video version.** It worked locally and in Lambda. FFmpeg is available when extraction is needed, but adds a large layer. [Groq supports MP4 input.](https://console.groq.com/docs/speech-to-text)

**A successful request still needs a quality check.** The cloud bullets included “algorithmic manipulation,” which the excerpt did not say. We proved the connection and output generation; strict grounding remains open.

**Keep these open questions visible:** longer or German recordings, chunking, concurrency, accuracy, retries/429s, application duplicate handling, and the frontend/orchestration were not tested.

## Where we stopped

- Groq total: **165 audio seconds, 2 LLM calls, 681 LLM tokens**, plus one model-list GET. No inference retries.
- AWS: **Free Plan active**; estimated cost before credits **$0**, with reporting lag. Credits moved from $100 to $120; we did not establish why.
- The owner **confirmed the temporary Groq key was revoked**.
- After the report and data were saved, the owner authorized AWS cleanup on **8 November 2026**. The test Lambda, layer version, S3 bucket and 16 objects, log group, and IAM role/policy were deleted; live absence checks passed. [Cleanup receipt](aws-cleanup.json)
- The owner then requested permanent copies of the input and generated data. Those are now archived in [data/](data/README.md), independently of S3 and the temporary directory.
- The original local scratch files remain under `.spike-tmp/`; this cleanup request covered AWS resources.

**Reading this report makes no API calls.** Replaying it is another experiment and needs a fresh temporary key and an agreed allowance. The current campaign still has only **435 audio seconds and 1 LLM call** left.

For exact identifiers, hashes, timestamps, and the formal checklist, use the [evidence record](../../docs/history/m1-fail-fast-spike.md).
