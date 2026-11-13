# 3 · Finish the experiment

[Cloud tests](02-cloud.md) → **FFmpeg, costs, and cleanup** → [Overview](README.md)

**Goal:** prove that Lambda can prepare audio itself, then leave a clear record of usage and remaining work.

## Step 1 — Get the Linux binary

The FFmpeg used on the laptop was a **Windows executable**. Lambda needed a **Linux x86_64 build**. That is why the earlier local clip preparation did not prove this step.

We downloaded a published wheel rather than building FFmpeg:

~~~powershell
python -m pip download --no-deps --only-binary=:all: --platform manylinux_2_28_x86_64 --dest .spike-tmp/cloud imageio-ffmpeg==0.8.1 --retries 0 --timeout 30
~~~

Its [PyPI file page](https://pypi.org/project/imageio-ffmpeg/0.8.1/#files) published the checksum we verified. The [upstream manifest](https://github.com/imageio/imageio-ffmpeg/blob/v0.8.1/tools/ffmpeg-sources.json) identifies the BtbN build.

| Check | Observed |
| --- | --- |
| FFmpeg version inside Lambda | `n9.0.2-17-g2a571b6068-20260930` |
| Executable size | 172,692,552 bytes |
| Build type | Static FFmpeg libraries; requires glibc >= 2.28 |
| License reported by `ffmpeg -L` | GPL version 3 or later |

The Python wrapper’s BSD license is not the bundled FFmpeg binary’s license. We recorded the binary license; a full distribution review remains later work.

**Checkpoint:** match the published wheel hash, then check version/license inside Lambda. A filename alone does not prove compatibility.

## Step 2 — Package a layer

A layer is a ZIP of supporting files that Lambda mounts under `/opt`.

Copy the packaging code in the [appendix](04-code.md#layer-packaging) into `.spike-tmp/cloud/package_layer.py`, then run:

~~~powershell
python .spike-tmp/cloud/package_layer.py
~~~

The ZIP contains `bin/ffmpeg` with Linux executable permission **0755**, plus a provenance notice. In Lambda, that becomes **`/opt/bin/ffmpeg`**.

| Package measurement | Observed |
| --- | --- |
| Layer ZIP | 67,981,539 bytes |
| Layer uncompressed | 172,693,322 bytes |
| Function + layer uncompressed | **172,702,328 bytes** |
| Limit checked | **250 MiB**, combined function and layers |

The compressed layer is above the 50 MB direct-upload limit, so we uploaded it to this same Region’s S3 bucket as `code/ffmpeg-layer.zip` and created the layer from S3. [Lambda package limits](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)

Publish a layer version compatible with **Python 3.13 / x86_64**, then attach that version to the function. Wait for the update to succeed.

During the session we also updated the handler to record `ffmpeg -L` and explicitly cap extraction at 55 seconds. The appendix preserves that final tested handler; a replay can use it from the start.

## Step 3 — Reserve one ASR call, then test WAV

Reserve **55 more audio seconds**, with **no LLM call**, using the appendix’s ledger snippet in `wav` mode. Our campaign total became **165 seconds / 2 LLM calls**.

Invoke once, synchronously:

~~~json
{"mode": "wav"}
~~~

The handler downloads and checks the same MP4, runs FFmpeg, inspects the WAV with Python’s `wave` module, and only then sends it to Whisper.

The essential extraction arguments were:

~~~text
-i /tmp/fixture.mp4 -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le -t 55 /tmp/fixture.wav
~~~

| Argument | What it does |
| --- | --- |
| `-map 0:a:0 -vn` | Select the first audio stream; omit video |
| `-ac 1` | Use one channel: mono |
| `-ar 16000` | Use 16,000 samples per second |
| `-c:a pcm_s16le` | Use uncompressed, signed 16-bit PCM audio |
| `-t 55` | Keep the output within the reserved duration |

**Observed:** 880,000 samples ÷ 16,000 = **55.0 seconds**, mono, two bytes per sample. WAV size was **1,760,078 bytes**.

Version/license checks plus extraction took **1.028 s**. Groq returned **HTTP 200 in 0.395 s**, with 16 timestamped segments. The transcript matched the MP4 result. Saved bullets were copied from the earlier run, byte-for-byte; there was no second cloud LLM request.

Handler time was **1.825 s**; Lambda billed **2.377 s**, including initialization/overhead. Max memory used was **149 MB**.

**Checkpoint:** inspect `output/wav-01/transcript.md`, `asr.json`, `metadata.json`, and `fixture.wav`. Confirm the exact audio format and compare the transcript with the direct-MP4 result.

## Step 4 — Add up everything

| Stage | Submitted audio | LLM calls | LLM tokens |
| --- | --- | --- | --- |
| Local MP4 test | 55 s | 1 | 326 |
| Cloud MP4 test | 55 s | 1 | 355 |
| Cloud WAV test | 55 s | 0 | 0 |
| **Total** | **165 s** | **2** | **681** |
| Campaign cap | 600 s | 3 | No separate token cap; max 1,024 completion tokens/request |

There was also **one model-list GET**. All inference calls returned HTTP 200; none were retried.

After the cloud tests, AWS still reported **FREE / ACTIVE**. Estimated usage before credits was **$0**, marked estimated; reported credits were **$120**. The two Lambda invocations billed a combined **4.077 GB-seconds** at 1 GB, plus S3/logging/control-plane activity.

**Do not read $0 as a final invoice.** Billing lags. Recheck AWS Settings → Billing after its next refresh, and keep the manual $1 stop.

## Small detours we hit

| What happened | What resolved it |
| --- | --- |
| Sandboxed upload could not connect | The approved network-enabled upload succeeded |
| Sandboxed pip found no matching distributions | The approved network-enabled download found the pinned Linux wheel |
| Cloud bullets added unsupported detail | We recorded it as a quality limitation; no reroll |

Neither local network issue established an AWS service-access failure. We encountered no paid-upgrade requirement for the tested path.

## Step 5 — AWS cleanup is complete

**Completed on 8 November 2026, 00:48 Vienna time:** after the report and data archive were saved, the owner explicitly requested AWS cleanup. All resources listed below were deleted and checked for absence. [Machine-readable cleanup receipt](aws-cleanup.json)

| Resource | Historical identifier | Result |
| --- | --- | --- |
| S3 bucket and all 16 objects | `studynotes-m1-588625038963-eun1-20261108` | Deleted; bucket returned 404 |
| Lambda | `studynotes-m1-spike-20261108` | Deleted; ResourceNotFoundException |
| Layer version | `studynotes-m1-ffmpeg-20261108:1` | Deleted; ResourceNotFoundException |
| CloudWatch Logs group | `/aws/lambda/studynotes-m1-spike-20261108` | Deleted; no matching group in either checked Region |
| IAM role / inline policy | `studynotes-m1-lambda-20261108` / `M1SpikeOnly` | Policy then role deleted; NoSuchEntity |

The cleanup order was function → layer version → S3 objects and bucket → role policy and role → log group. Removing the function first prevents further work from writing new output or logs. Before deletion, we verified all 23 retained data artifacts against their checksums and confirmed the bucket held only the expected spike files, with no versions or unfinished uploads.

The final checks deliberately queried the deleted resources. Their specific “not found” responses confirmed removal; an access-denied error would not have proved that. Log-group checks returned no matches in `eu-north-1` or `us-east-1`. The final cost query still reported **estimated $0 before credits**, with billing lag.

The original local scratch files under `.spike-tmp/` remain; the user requested AWS cleanup. No CloudShell files were created in this cloud run.

The input and generated results are now permanently preserved in [this report’s data archive](data/README.md), including both cloud runs and the earlier local results. Keep that entire folder during cleanup.

Keep the AWS project, this report and its data archive, the evidence record, and the requested Groq script. Revoke the temporary Groq key at the provider too; deleting Lambda alone would not revoke it. The owner has already confirmed that provider-side step for this session.

**What this enables next:** plan the short-video path with evidence. Assign owners and follow-up tests to the unproven parts before claiming the full application’s KPIs.
