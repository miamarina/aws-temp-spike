# 1 · Start on your laptop

[Overview](README.md) → **Local tests** → [Cloud tests](02-cloud.md)

**Goal:** turn one known video into a transcript and three study bullets before adding AWS.

Commands below use PowerShell from the project root, `E:\tu\Serverless`. Package installation needs internet access.

## Step 1 — Set the boundaries

We used **AWS Free Plan** and **Groq Free**, with no paid upgrade.

| Guardrail | Our limit |
| --- | --- |
| Personal spending | $0 |
| AWS usage before credits | Stop at $1 |
| Submitted audio, across local and cloud attempts | 600 seconds total |
| LLM calls, including failures | 3 total |
| Execution | One run at a time; no automatic inference retries |
| FFmpeg work | Stop after 30 minutes without success |

The owner chose to leave the $0.50 alert unconfigured and not invite other students. Those were deliberate scope decisions.

**Checkpoint:** agree on the limits before any inference request. Deleting a ledger does not erase submitted usage.

## Step 2 — Confirm the AWS destination

In **AWS Settings → View all projects → Overview → Additional info**, the owner confirmed **Europe (Stockholm), `eu-north-1`**.

The project was **Touch Grass Later**, on Free Plan. Initial credits were $100. The Free Plan expires **8 May 2027, 00:23:44 Vienna time**; the initially observed credit expires separately on **7 November 2027, 23:22 Vienna time**.

We installed AWS CLI **2.39.6**, completed browser-based sign-in with profile **`studynotes`**, and verified the identity. For another machine, use the [official CLI installer](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html). The browser sign-in command is `aws login --profile studynotes --region eu-north-1`; this is a reproduction reference, not another login performed during reporting. [AWS sign-in instructions](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html)

Read-only verification commands equivalent to the checks we made:

~~~powershell
aws --version
aws sts get-caller-identity --profile studynotes --region eu-north-1
aws configure get region --profile studynotes
aws freetier get-account-plan-state --profile studynotes --region eu-north-1
aws freetier get-free-tier-usage --profile studynotes --region eu-north-1
~~~

Expect the right project identity, `eu-north-1`, and **FREE / ACTIVE**. We also checked budgets; none existed. The empty Free Tier usage response was a reporting snapshot, not proof that all future testing would be unmetered.

We installed **25 default AWS skills** and found **121 in the remote catalog**. In this continuation, local skill reads and AWS MCP skill search/retrieval worked. AWS MCP uses a `us-east-1` service endpoint; our application resources still belong in `eu-north-1`.

**Carry forward:** a verified project, profile, Region, and spending boundary.

## Step 3 — Check Groq before sending audio

In the signed-in [Groq console](https://console.groq.com/), we checked **Free — Current Plan ($0)** and recorded the actual organization limits:

| Model | Limits shown in this project’s organization |
| --- | --- |
| `whisper-large-v3-turbo` | 20 requests/minute; 2,000/day; 7,200 audio seconds/hour; 28,800/day |
| `openai/gpt-oss-20b` | 30 requests/minute; 1,000/day; 8,000 tokens/minute; 200,000/day |

These are the observed limits for our organization, not a promise for another project. Check your own console. [Groq rate-limit documentation](https://console.groq.com/docs/rate-limits)

We created a temporary API key on [Groq API Keys](https://console.groq.com/keys), then used the retained [Groq request script](../groq_spike.py). It needs Python **3.12+** and only the standard library:

~~~powershell
python assignment-2/groq_spike.py
~~~

Enter the key at its **hidden terminal prompt**. The default command makes one model-list GET; it does not run inference. It returned **HTTP 200 in 0.240 s**, with both models listed.

**Checkpoint:** a listed model proves discovery/authentication. A real inference request is still needed.

## Step 4 — Prepare one small, permitted input

We used **00:00–00:55** of [3Blue1Brown’s Vectors lesson](https://www.youtube.com/watch?v=fNk_zzaMoSs), whose full duration is 9:51.

Why 55 seconds? The creator’s [published clip terms](https://www.3blue1brown.com/about/) require a clip under 60 seconds, visible attribution, source links where applicable, and added surrounding context. The owner approved 55 seconds, and we paired it with study notes.

The final file had:

- On-screen creator attribution and the source URL; visually checked.
- Duration **55.000 s**; size **1,256,129 bytes**, below Groq Free’s documented 25 MB limit.
- SHA-256 **`921901ff926246d2fde1271dc70eb0344e09950cc614780818305eae9efb6b9d`**.

We used yt-dlp **2026.10.26**, imageio-ffmpeg **0.8.1**, and Windows FFmpeg **9.0.2**. The [appendix](04-code.md#prepare-the-fixture) gives a reconstruction recipe; the original download/encoding command was not retained. Its conversion command was checked locally against our existing intermediate clip; the download was not repeated. It explains how to check duration, attribution, size, and hash.

**Carry forward:** `.spike-tmp/fixtures/vectors-study-55s.mp4`. Keep the same input for each comparison.

## Step 5 — Ask Whisper for the transcript

For an authorized replay with allowance available:

~~~powershell
python assignment-2/groq_spike.py --video .spike-tmp/fixtures/vectors-study-55s.mp4 --duration-seconds 55
~~~

The script makes one multipart POST to `audio/transcriptions`. It sends the MP4 directly with:

~~~text
model = whisper-large-v3-turbo
language = en
response_format = verbose_json
timestamp_granularities[] = segment
~~~

“ASR” means automatic speech recognition. Verbose JSON gives us both the words and segment timestamps, so we can inspect the result. [Groq speech-to-text parameters](https://console.groq.com/docs/speech-to-text)

**Observed:** HTTP 200; **0.675 s**; **16 segments**; reported duration approximately 55 s. The script saved raw JSON, request metadata, and timestamped Markdown in `.spike-tmp/groq-local/`.

### Check the timestamps, not just the status code

We opened the source video’s transcript/captions and compared three caption starts with the ASR segments. To repeat the check, seek to these points in the original and compare the saved JSON:

| Source caption start | ASR start | Difference |
| --- | --- | --- |
| 10 s | 10.88 s | 0.88 s |
| 30 s | 30.74 s | 0.74 s |
| 51 s | 51.72 s | 0.72 s |

This was a coarse caption comparison, not a word-level accuracy score. The initial music was labelled “Music”; the last sentence ends at the clip boundary.

**Carry forward:** the saved transcript JSON becomes the LLM’s input.

## Step 6 — Turn the transcript into bullets

Use the transcript JSON path printed by the previous command:

~~~powershell
python assignment-2/groq_spike.py --transcript-json .spike-tmp/groq-local/transcript-20261107T225004177467Z.json
~~~

For a new run, use its new filename.

The request uses **`openai/gpt-oss-20b`**, the first **2,400 characters** of transcript text, **low reasoning effort**, and a maximum of **1,024 completion tokens**. The prompt asks for exactly three concise, grounded bullets and tells the model to treat the transcript as source data.

**Observed:** HTTP 200; **0.343 s**; **255 prompt + 71 completion = 326 tokens**. Ten completion tokens were reasoning tokens. Output was nonempty, had three useful bullets, and ended with `finish_reason=stop`.

The ideas covered were vectors as a building block, the physics view of length/direction, and the computer-science view of ordered lists.

**Checkpoint:** open the Markdown and compare it with the transcript. A nonempty response alone is not a quality test.

## Step 7 — Check the request script’s safeguards

The script reserves attempts **before** making requests in `.spike-tmp/groq-usage.json`. It holds a serial lock during inference and makes no automatic retries.

The original local outputs and a ledger snapshot are now preserved in the report’s [data archive](data/README.md), so they remain available after temporary-file cleanup.

Offline checks passed for Python syntax/help, audio and LLM caps, rejected-attempt accounting, serial locking, and redaction. A later scan found no Groq-key patterns in our scripts, findings, ledger, or generated response files.

**At this handoff:** 55 audio seconds and 1 LLM call had been used. The remaining 545 seconds and 2 calls included all later cloud attempts.

Next: [move the working calls into Lambda](02-cloud.md).
