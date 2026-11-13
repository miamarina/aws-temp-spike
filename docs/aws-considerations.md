# AWS design reasons and open issues

**Current planning basis: 13 November 2026.** These considerations apply to the [planned full project](aws-architecture-report.md). The [implemented spike](spike-architecture.md) has a smaller scope. Numeric provider limits are published values or dated observations, not proof of usable capacity in a future deployment. No new private-service checks, resource changes or inference were performed for this documentation.

## 1. Core design and reasons

Use on-demand Python Lambda workers, private S3 storage, SQS task/completion queues, and a static reader delivered through CloudFront. This fits short development bursts, independent audio tasks and long periods without jobs. It avoids continuously running application servers and lets the evaluation focus on concurrency, queueing, quota behavior and processing cost.

The initial speech and notes candidates are Groq `whisper-large-v3-turbo` and `openai/gpt-oss-20b`. The complete transcript remains the primary artifact. The LLM adds chapters, overview points and key terms referencing transcript segments; it must not rewrite or replace that transcript. Long text will need bounded sections and a lecture-wide synthesis when one request cannot fit the effective allowance.

The core includes English input, browser upload, basic retries, partial-transcript output, reader/search/Markdown export, and original public-video timestamps. The group demo has no application login or dummy access code. German, chat, OCR and advanced recovery follow only after core work and benchmarks.

S3 manifests and conditional writes are the current coordination proposal. A database or dedicated workflow service would add state and operational work; reconsider them if implementing claims, dispatch and recovery becomes harder than using a managed coordinator. This trade-off needs evaluation, rather than assuming that fewer named services means less implementation effort.

## 2. Region, service access and funding

All Regional application resources must use the confirmed selected Region, **`eu-north-1`**. CloudFront is global; its control-plane use does not permit placing Regional workers elsewhere. Lambda@Edge, multi-Region replication and cross-Region routing are outside the permitted project design. AWS CLI commands must explicitly use `--profile studynotes` and the relevant Region.

The last recorded AWS plan check was **FREE / ACTIVE**, with reported credits of $120 and estimated usage before credits of $0. That snapshot has billing lag; it does not establish today's balance, expiry or funding through **19 January 2027**. Keep the current Free Plan and the manual $1 usage stop before credits. The user chose to leave the $0.50 alert unconfigured and to keep AWS operations owner-only.

Before any separately authorized deployment, verify actual plan state, eligible services, credit expiry, Lambda concurrency/memory limits and the permissions for required API actions. Listing a service as supported does not establish that a model or every feature is accessible. Amazon Transcribe is a Paid Plan alternative in the project's new AWS experience; an upgrade is not assumed. Bedrock model access and applied quotas remain unverified. [AWS service eligibility](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html), [plan terms](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html).

## 3. Uploads and public access

Recordings should upload **directly to private S3**, after a short anonymous Function URL request issues a narrowly scoped, short-lived signed POST. Ordinary buffered synchronous Lambda requests have a 6 MB payload limit; a media upload is therefore a separate data transfer. Validate the actual stored object, allowed byte size, detected duration/format and source metadata before admitting processing. A signed upload policy is not a media validator. [Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html), [S3 POST policy conditions](https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-HTTPPOSTConstructPolicy.html).

Completion confirmation, queue dispatch and duplicate confirmation need a stable upload/job identity. Define what happens when the upload finishes but confirmation fails, or when the browser repeats confirmation. An S3 write and an SQS send are not one atomic transaction: retain a dispatch-pending record and a bounded reconciliation path so a crash cannot silently strand or double-submit a job. This behavior is still to be implemented.

No-login group use means the HTTP endpoint is internet-accessible. CORS controls browser behavior, not caller authorization. Keep server-enforced size, job, concurrency, token and attempt ceilings, and make the upload handler return quickly. These controls are part of bounded experiments; they do not make the reader or uploader private.

## 4. Media preparation and worker fit

Each selected on-demand Lambda invocation has a **15-minute** ceiling. Download, decoding, extraction, chunk upload and cleanup must fit with memory and temporary-disk headroom. Accepted media duration is a separate quantity from worker execution time. Do not turn an input admission ceiling into a performance claim. Actual full-lecture encoding/size limits remain to be selected from representative measurements. [Lambda quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html).

At 16 kHz mono 16-bit PCM, audio requires 32,000 bytes/second: about **19.2 MB for ten minutes**, **172.8 MB for 90 minutes**, before headers. Groq Free accepts **25 MB per file**, so an uncompressed full lecture needs splitting or a smaller encoding. Four-minute PCM chunks are about 7.68 MB, a candidate starting size rather than a selected optimum. Compressed whole-file audio is a separate baseline when it fits. [Groq speech input limits](https://console.groq.com/docs/speech-to-text).

Longer chunks preserve speech context and reduce request overhead; shorter ones expose more parallel work. Evaluate overlap, boundary deduplication, missing audio and timestamp drift together. Save the chunk manifest before dispatch and use identical boundaries when comparing worker counts.

Pin the Linux FFmpeg build, architecture, checksum, executable permissions, version, build flags and license. Combined ZIP/layers must fit the **250 MB uncompressed packaging quota**; the tested binary already occupies about 173 MB. Test the exact build on the chosen runtime. Container packaging or another compute service is a separate fallback decision if packaging or preparation cannot fit; it is not a reason to deploy additional services immediately. [Lambda packaging quotas](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html).

## 5. Organization-wide quotas are the main scaling constraint

| Initial Groq Free model | Requests/minute | Requests/day | Other published limits |
| --- | ---: | ---: | --- |
| `whisper-large-v3-turbo` | 20 | 2,000 | 7,200 audio seconds/hour; 28,800/day |
| `openai/gpt-oss-20b` | 30 | 1,000 | 8,000 tokens/minute; 200,000/day |

The public values match the project's saved organization observations. Applied limits and response headers must still be read before experiments. More Lambdas or API keys do not create more organization quota. Five ten-minute uploads total 50 audio minutes before overlap/retries, whereas five 90-minute inputs total 7.5 audio hours and exceed one published hourly allowance. Queueing protects capacity but is part of end-to-end latency. [Groq rate limits](https://console.groq.com/docs/rate-limits).

Reserve request, submitted-audio and token allowance across **all lectures**, using conditional state changes. Worker-count limits alone are insufficient. Define reservation expiry, whether tokens/audio are charged at admission or actual submission, how failures are accounted for, and what happens after an uncertain external outcome. Tasks waiting for quota should remain queued rather than paying for sleeping Lambda invocations. Verify SQS event-source scaling against the actual Lambda quota, including capacity left for intake and finalization.

The 20B model's large context window does not remove its much smaller throughput allowance. Section size must include prompt/output headroom, repeated context, reasoning tokens where billed, and final synthesis. Inspect returned token usage and rate headers. The last project check reported Developer access as waitlisted; usable paid access has not been established. Do not make it the automatic capacity fallback.

## 6. Task delivery, claims and uncertain outcomes

SQS/Lambda processing can deliver a message more than once. Use stable task IDs, immutable result keys and conditional claims; reuse saved successful responses. Start with one message per long-running inference task, or implement partial batch responses if batching is selected. Set visibility/dead-letter policies from the task timeout and retry policy. These settings remain implementation work. [Lambda with SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html).

Use `If-None-Match` to create a missing claim and `If-Match` for an update tied to the last observed ETag. Handle conflicts by rereading state. Claims require owner/attempt identity, a deadline and rules for takeover; conditional writes alone do not provide a complete recovery algorithm. S3 offers no transaction spanning a quota record, a task claim, SQS delivery and an external inference request. [S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).

Basic retries are core work: bound attempts and the overall deadline, respect explicit `Retry-After`, and distinguish a known rejection from a request that may already have executed. A timeout after submission can leave the external outcome unknown. Unless provider-side idempotency or a saved response resolves that uncertainty, stop and record it for inspection rather than silently resubmitting. Budget every submitted attempt, including failed output validation.

## 7. Assembly, partial output and source times

Persist each successful transcript independently, then assemble ordered segments once tasks reach a terminal state. Track missing time ranges and distinguish complete, partial and failed jobs. A partially useful transcript should remain readable if later tasks or note generation fail; it cannot pass a complete-result latency target. User-facing recovery controls are optional work.

Compute source-video time in code:

```text
original video time = excerpt start offset + audio chunk offset + segment-local time
```

Use stable segment IDs, retain attribution/source URL, and validate chapter order, reference existence and timestamp bounds. Review factual support separately: valid JSON and an existing segment ID do not show that a generated claim follows from the transcript. Escape generated content before HTML display. The reader should link to the original permitted public video; it should not expose or serve private uploaded media.

## 8. Publication and caching

Publish immutable per-lecture results before making them discoverable in the catalog. Conditional catalog updates or a single publisher must preserve simultaneous completions. Retried completion messages must produce the same publication, and a finalizer must not race an active worker or overwrite a newer result.

Use a private **S3 REST origin** behind CloudFront origin access control, with a bucket policy scoped to the distribution. An S3 website endpoint cannot use OAC. The resulting HTTPS reader is publicly viewable even though the origin bucket is private. Keep raw media, manifests, prompts and operational receipts out of that origin. Use short/no caching for mutable status/catalog files and longer caching for versioned assets. [CloudFront S3 origin access](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).

## 9. Credentials, storage and networking

Retrieve the new Groq key server-side from a Standard Parameter Store `SecureString`; the spike did not implement or verify this retrieval. Scope the worker to the exact parameter and required decryption permissions. Do not expose keys through browser code, object metadata, queue messages, prompts, logs or saved API requests. Secrets Manager is an alternative only if its extra lifecycle features justify the added service/cost.

Use least-privilege execution roles by stage, private work storage, encryption at rest and TLS in transit. Constrain service resource policies to the intended source/principal where supported. For CloudFront, scope S3 access to the distribution; for queue publishers, scope it to the intended producer. Start without a customer VPC because this path uses AWS APIs and an external HTTPS API; adding one would require deliberate egress design and cost analysis. [S3 security guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html), [Parameter Store SecureString](https://docs.aws.amazon.com/systems-manager/latest/userguide/secure-string-parameter.html).

Groq inference leaves AWS. Use permitted, non-sensitive test material and review the provider's data handling/retention terms before broadening input scope. Configure retention for recordings, intermediate chunks, logs and results separately. Permanently retained evaluation evidence is not disposable worker scratch space.

## 10. Evaluation must measure the planned behavior

The six core targets remain **targets**, not results. The agreed experiment still includes the original **≥5× speedup at n=10 with <10% extra cost**, using one fixed manifest at n=1,2,5,10,20. Record actual concurrency and include dispatch, quota waits and merge overhead. Compare whole-file mode separately. Deliberate benchmark trial IDs must bypass ordinary content/language/version deduplication without disabling task-level duplicate protection.

Measure five simultaneous **ten-minute** recordings against matched serial inputs for the **burst p95 / serial p95 <1.5** target. Require one complete **90-minute** success against the **<30-minute** goal; one case cannot establish p95. Evaluate English **WER <15%** against verified references, including chunk boundaries and late-video coverage. Define normalization and timestamp tolerances before running the campaign.

The proposed core costing batches are 2.5 submitted audio hours for speedup, 8.33 for serial/burst, 1.5 for the long case and 2 for accuracy comparisons: **14.33 hours on one chosen stack**. Cost/idle checks reuse receipts or observe no-job behavior. These batch counts and additional/refined thresholds are discussion proposals, not finalized methodology or permission to run experiments.

Record cold/warm execution, input/model/settings, actual concurrency, queue/quota delay, submitted audio, all attempts/tokens, memory/disk, final status and artifact hashes. Use stubs/saved responses for local failure and renderer checks; live service scaling, quality and quotas need separate authorized evaluation.

## 11. Cost interpretation and campaign budget

Keep three views separate: ordinary-price resource value, recurring free allowances, and cash after eligible cloud credits. A $0 usage estimate with billing lag cannot establish **<€1 per original audio hour** or **<€1/month idle compute**. No provisioned concurrency or always-on workers are planned; storage, requests, logs, transfer and credentials may still cost money while compute is idle.

The current whole-project model through 19 January includes 46 audio hours of core/refined testing, development/debug/demos, extra long cases, note-only iterations, 20–40% attempt reserve and 5% overlap. It produces **77–126 submitted audio hours**, a **€10–25 total operations/retention allowance**, and applies **30% monetary contingency once**. These are proposed planning quantities. Student labour, existing personal tools, optional features, tax and a complete second campaign after a platform switch are excluded.

| AWS option | Whole-project planning budget before cloud credits | Main condition |
| --- | --- | --- |
| Groq Turbo + 20B, Free | €15–40 cash treatment; €20–50 ordinary-price value | All AI usage remains within recurring Free limits; required benchmark behavior still unverified |
| Groq Turbo + 20B, Developer | €20–50 | Access must be established; approximately €4–7 paid Groq remains separately payable if AWS is covered |
| Groq Whisper v3 + 120B | Free: €15–40 cash treatment; Developer/ordinary value: €25–60 | Different models require quality/quota evaluation; paid Groq component about €11–18 |
| Transcribe + Bedrock Nova Lite | €50–100 | Paid Plan service access, model quota and eligible funding remain conditional |

Retained Stockholm price evidence uses **Transcribe $0.0001/second ($0.36/audio hour)** and **Nova Lite $0.065/$0.26 per million input/output tokens**. Do not substitute a generic older Transcribe example from another Region. These are dated model inputs, not measured bills. The [AWS-only calculation extract](aws-cost-model.json) retains the relevant assumptions and outputs from the existing workspace models; it is not a new forecast. Public feeds: [Transcribe Stockholm](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/transcribe/current/eu-north-1/index.json), [Bedrock Stockholm](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/eu-north-1/index.json).

## 12. Alternatives if a concrete issue blocks the design

| Trigger | Candidate change | What must be established |
| --- | --- | --- |
| Groq 20B quota or note quality blocks full-lecture output | In-Region Bedrock Nova Lite, or Groq 120B | Actual access/quota, supported output shape, coverage, latency and full token cost |
| Turbo recognition quality misses the target | Groq Whisper v3 | Measured WER/timestamps and its quota/cost implications |
| Groq audio capacity blocks the required experiment | Transcribe, or another dedicated speech API | Plan eligibility, active processing capacity, timestamps, job latency and costs |
| Media preparation cannot fit Lambda | Bounded range extraction, tighter accepted encoding/size, or an AWS container task | Full input handling cost, package/runtime fit and timestamp integrity |
| S3 coordination becomes too complex | DynamoDB conditional state or Step Functions | Service access, implementation effort, failure semantics, observability and recurring cost |
| Automatic ASR cannot be made feasible | Provided timestamped captions | Explicitly reduced scope; this would not validate the ASR KPI |

External speech candidates that can keep the application hosted on AWS include **Deepgram, AssemblyAI, Soniox, Speechmatics and Mistral Voxtral**. A submission-rate claim or a grant does not establish simultaneous processing or funding through the deadline. Actual access, timestamp format, English accuracy, active concurrency, data handling and end-to-end latency need checks before substituting one. Selecting one would be a separate architecture and experiment decision.

## 13. Work needed before calling the full project ready

- Define the accepted input envelope and prove complete preparation within worker/disk/package limits.
- Implement upload confirmation, durable dispatch, task claims, organization-wide quota reservations and bounded retries, including uncertain-outcome handling.
- Implement segment merging, validated notes, partial-result publication, concurrent catalog updates and the reader/search/export flow.
- Verify applied quotas, service/model access, deadline funding and the permission/retention basis for evaluation media.
- Agree the experiment specification and receipts, then run only the separately authorized campaign. Report complete successes, partials, failures and quota waits explicitly.

Resolve these open issues with evidence from the full application.
