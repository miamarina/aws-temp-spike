# 2 · Prove the cloud path

[Local tests](01-local.md) → **Cloud tests** → [FFmpeg and cleanup](03-ffmpeg-and-cleanup.md)

**Goal:** make the known local path work inside AWS, using the same clip and models.

We used AWS MCP for resource operations and short-lived presigned URLs for file uploads. Below is an equivalent console walkthrough so a student can follow the same experiment. The console recipe itself was not separately replayed.

## Step 1 — Recheck the plan and cost

Before creating resources, we checked the AWS identity, Free Plan, credits, Free Tier usage, and estimated cost.

**Observed:** FREE / ACTIVE, $100 credits, no Free Tier usage entries, estimated **$0 before credits**.

The cost query used `UnblendedCost`, excluded Credit/Refund records, and covered **1–7 November UTC**. Credit balance and usage are separate measurements: credits can cover usage.

**Checkpoint:** stop if the route needs an upgrade or reported usage before credits reaches $1.

## Step 2 — Make a private place for the files

In the S3 console, select **`eu-north-1`** and create one general-purpose test bucket.

For a future authorized experiment, choose unique resource names. We tagged the bucket/function with `Purpose=m1-fail-fast-spike` and `Cleanup=after-spike` to make the temporary resources easy to identify.

| Setting | Our choice | Why |
| --- | --- | --- |
| Object Ownership | Bucket owner enforced; ACLs disabled | Manage access with policies |
| Block Public Access | All four flags on | Keep the experiment private |
| Default encryption | SSE-S3, `AES256` | Encrypt stored files |
| Bucket policy | Deny non-TLS requests | Require encrypted transport |

The [appendix has the bucket policy](04-code.md#bucket-policy-require-tls). These settings follow [S3 security guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html).

We uploaded the checked clip as:

~~~text
input/vectors-study-55s.mp4
~~~

S3 “folders” are key prefixes. That exact key matters because the handler reads it.

**Carry forward:** the bucket name and input key become the Lambda configuration.

## Step 3 — Give Lambda only the permissions it needs

A Lambda execution role is the permission set its code uses while running. It is separate from your own signed-in access.

Create an IAM role using the appendix’s custom trust policy for **`lambda.amazonaws.com`**, with no managed permission policies. Add the [scoped inline policy](04-code.md#lambda-role). It allows:

- Reading this input MP4 and the earlier saved bullets.
- Writing only under `output/` and `attempts/` in this bucket.
- Creating streams and writing events in this Lambda’s log group.

Create the CloudWatch Logs group `/aws/lambda/YOUR_FUNCTION_NAME` before invoking. We set retention to **1 day**. The scoped role does not need permission to create arbitrary log groups.

We used the documented [Lambda execution-role trust pattern](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html). No human/team-member permissions were changed.

**Carry forward:** Lambda can now read its input and save results without making the bucket public.

## Step 4 — Package and create the function

Copy the [tested handler from the appendix](04-code.md#lambda-handler) into `.spike-tmp/cloud/lambda_function.py`. It uses Python’s standard library plus boto3/botocore supplied by the Lambda Python runtime.

The handler verifies the MP4’s SHA-256. If you recreated the clip, set `EXPECTED_SHA` to your verified new file’s hash; re-encoding can change the bytes.

Package **the file at the ZIP root**:

~~~powershell
python -c "import zipfile; z=zipfile.ZipFile('.spike-tmp/cloud/function.zip','w',zipfile.ZIP_DEFLATED); z.write('.spike-tmp/cloud/lambda_function.py','lambda_function.py'); z.close()"
~~~

Create a Lambda in **`eu-north-1`**, choose the execution role, and upload the ZIP.

| Setting | Exact value |
| --- | --- |
| Runtime / architecture | Python 3.13 / x86_64 |
| Handler | `lambda_function.handler` |
| Memory / ephemeral storage (`/tmp`) | 1,024 MB / 1,024 MB |
| Timeout | 300 seconds |
| VPC | No VPC configuration |
| Triggers / Function URL | None |

Add environment variable **`SPIKE_BUCKET`** with the bucket name. Add the temporary **`GROQ_API_KEY`** directly in the console, then save. The owner did this; our configuration checks returned only whether the key existed.

Wait until the function is **Active** and the last update **Successful**.

**Why no trigger yet?** A manual test gives us control over exactly when a scarce external call happens.

## Step 5 — Count first, invoke once

Before the cloud test, we reserved **55 audio seconds and 1 LLM call** in the campaign ledger. That brought the reservation to **110 seconds / 2 calls**, including the earlier local tests.

Cloud submissions must be added to that same campaign total; the local request script cannot observe them automatically. The appendix includes the exact reservation snippet.

Create this Lambda test event and invoke it **synchronously once**:

~~~json
{"mode": "mp4"}
~~~

The code follows this chain:

~~~text
Read MP4 from S3 → verify hash → POST to Groq Whisper
→ save ASR JSON + transcript Markdown
→ POST transcript excerpt to Groq LLM
→ save LLM JSON + bullet Markdown + timing metadata
~~~

Before each external POST, the handler conditionally creates an S3 attempt marker. An existing marker blocks another submission for that fixed run. This protects this experiment; it is not a full application duplicate-handling test.

There are no automatic HTTP or S3 retries in the handler. We configured no asynchronous source. Do not switch this experiment to asynchronous invocation.

**Important:** an Invoke HTTP 200 only means Lambda accepted/returned the request. Also inspect the handler’s **`status`**, which must be **`pass`**.

## Step 6 — Open the actual output

Look under `output/mp4-01/`:

Retained local copies are linked in the [data index](data/README.md#inspect-the-raw-cloud-results); they can be opened without AWS access.

| File | What it tells you |
| --- | --- |
| `asr.json` | The original transcription response |
| `transcript.md` | Words and segment times you can read |
| `llm.json` | Bullet response, token usage, finish reason |
| `bullets.md` | The three study bullets, with source attribution |
| `metadata.json` | Status, timings, runtime, request ID |

We opened all five objects. The transcript was usable; all objects reported AES256 encryption.

| Measurement | Observed |
| --- | --- |
| S3 input download | 0.116 s |
| Groq ASR | HTTP 200; 0.442 s; 16 segments |
| Groq LLM | HTTP 200; 0.474 s; `finish_reason=stop` |
| LLM tokens | 255 prompt + 100 completion = **355** |
| Handler / Lambda billed duration | **1.271 s / 1.700 s** |
| Max memory used | 98 MB |

CloudWatch logged status and timing, not the key or full request bodies.

### Pause for the quality check

The cloud output had exactly three bullets, but introduced “algorithmic manipulation” beyond the transcript. We recorded that limitation rather than spending another call to reroll it.

**Carry forward:** the core cloud path works. Keep its saved bullets: the FFmpeg test can reuse them and avoid another LLM call.

Next: [extract WAV inside Lambda, then finish safely](03-ffmpeg-and-cleanup.md).
