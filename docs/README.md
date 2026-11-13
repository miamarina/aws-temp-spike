# AWS architecture documentation

This folder explains the retained AWS spike implementation, the reasons for its design, the planned full application, and the issues that still need resolution. It contains current descriptions and the current proposal only.

## Start here

| Document | Purpose | Status |
| --- | --- | --- |
| [Spike architecture](spike-architecture.md) | What the code does, its configuration, why it is deliberately small, and its limits | Implemented code and saved outputs; the cloud resources have been removed |
| [Full-project architecture](aws-architecture-report.md) | Proposed components, processing flow, scope and required benchmarks | Planned; not deployed or validated by the spike |
| [AWS considerations and open issues](aws-considerations.md) | Design reasons, quota/resource constraints, failure handling, alternatives, evaluation and budget | Current planning guidance; unresolved points are explicit |

The planned architecture has a [PNG diagram](aws-architecture-report.png), [SVG diagram](aws-architecture-report.svg) and editable [PlantUML source](aws-architecture-report.puml). These all describe the **full project**, not the spike.

## What exists and what is planned

| Area | Implemented spike | Planned full project |
| --- | --- | --- |
| Starting work | Operator uploads one fixed input to S3 and invokes Lambda manually | Browser obtains signed upload permission, uploads directly to S3 and confirms completion; backend validates and queues work |
| Processing | One Python Lambda executes a fixed MP4 or WAV path | Bounded preparation, transcription, merge, notes and publication tasks |
| Coordination | Fixed run IDs and conditional attempt markers | SQS task/completion queues, S3 manifests, conditional claims and shared quota reservations |
| Speech and notes | Groq Turbo transcription, then three bullets from GPT-OSS-20B; WAV mode reuses saved bullets | Same initial model candidates; complete transcript plus chapters, overview and terms, sectioned when quotas require |
| Audio preparation | Optional Linux FFmpeg layer extracts 55 seconds of WAV | Validate and prepare complete recordings; evaluate whole-file versus parallel chunks |
| Output | Markdown, raw JSON and timing metadata | Static reader, lecture catalog/search, Markdown export and original-video timestamp links |
| Reader hosting | No reader or CloudFront distribution | Private S3 reader origin behind public CloudFront HTTPS |
| Secret handling | Handler expects a temporary environment key; that key is revoked | Retrieve the Groq key server-side from Parameter Store SecureString |
| Reliability | No automatic retries; fixed attempt markers stop repeated submission | Basic bounded retries, duplicate handling, saved partial transcripts and terminal failure records |
| Demonstrated scope | One 55-second English fixture; saved integration outputs | English core, five simultaneous ten-minute recordings, a complete 90-minute case, and the required parallel-speedup experiment |

**There is no running AWS application to use at present.** The source, tested handler appendix and saved outputs remain available. Reading them makes no service calls. The planned components are not implied by the retained source or diagram.

## Code and supporting material

- [Lambda handler](../lambda_function.py), [local request script](../groq_spike.py) and [code-folder entry point](../README.md).
- [Function/FFmpeg layer packager](../package_layer.py), [package upload helper](../../../projects/aws-groq-spike/upload.py), [policy templates](../policies/README.md), and invocation events for [MP4](../events/mp4.json) / [WAV](../events/wav.json).
- [Code and policy explanation](../04-code.md).
- [Saved input/output index and checksum manifest](../data/README.md).
- [Cloud configuration and output details](../02-cloud.md) and [FFmpeg configuration](../03-ffmpeg-and-cleanup.md).
- [Resource-removal receipt](../aws-cleanup.json).

The application design is for a group demo and controlled experiments. The prospective full-project brief stands on requirements and expected trade-offs; the spike outputs are supporting implementation evidence, not results for the planned benchmarks. Documentation does not authorize deployment, paid upgrades or new inference.
