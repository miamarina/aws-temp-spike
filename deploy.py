"""Plan offline or deploy the single-function spike with AWS CLI; never invoke it."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent
REGION = "eu-north-1"
FIXTURE_SHA256 = "921901ff926246d2fde1271dc70eb0344e09950cc614780818305eae9efb6b9d"
CONFIG_KEYS = {"profile", "region", "project_id", "bucket_name", "function_name", "role_name", "layer_name"}


class DeploymentError(RuntimeError):
    pass


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if set(config) != CONFIG_KEYS or not all(isinstance(v, str) and v.strip() for v in config.values()):
        raise ValueError("Config must contain exactly the seven nonempty string fields in config.example.json; no secrets")
    if config["region"] != REGION:
        raise ValueError("This project deploys only to its confirmed selected Region eu-north-1")
    if not re.fullmatch(r"\d{12}", config["project_id"]):
        raise ValueError("Replace project_id with the intended 12-digit AWS project ID")
    bucket = config["bucket_name"]
    if not re.fullmatch(r"studynotes-spike-[a-z0-9][a-z0-9-]{0,44}[a-z0-9]", bucket):
        raise ValueError("Use a unique 18-63 character bucket name starting with studynotes-spike-; lowercase letters, digits and hyphens only")
    for key in ["function_name", "role_name", "layer_name"]:
        if not re.fullmatch(r"studynotes-spike-[A-Za-z0-9_-]{1,48}", config[key]):
            raise ValueError(f"{key} must start with studynotes-spike- and contain at most 64 letters/digits/hyphens/underscores")
    return config


def plan(config):
    return {
        "profile": config["profile"], "region": REGION, "expected_project_id": config["project_id"],
        "bucket": config["bucket_name"], "function": config["function_name"],
        "role": config["role_name"], "layer": config["layer_name"],
        "log_group": "/aws/lambda/" + config["function_name"],
        "runtime": "python3.13", "architecture": "x86_64", "memory_mb": 1024,
        "temporary_storage_mb": 1024, "timeout_seconds": 300,
        "requires_plan": "FREE / ACTIVE", "sets_groq_key": False,
        "invokes_function": False, "creates_trigger_or_function_url": False,
    }


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_build():
    output = ROOT / ".build"
    metadata = json.loads((output / "layer-metadata.json").read_text(encoding="utf-8"))
    if metadata["function_source_sha256"] != sha256(ROOT / "lambda_function.py"):
        raise ValueError("Source changed since packaging; rebuild first")
    for name, key in [("function.zip", "function_zip_sha256"), ("ffmpeg-layer.zip", "layer_zip_sha256")]:
        if metadata[key] != sha256(output / name):
            raise ValueError(f"Package checksum mismatch: {name}")
    with zipfile.ZipFile(output / "function.zip") as package:
        if package.namelist() != ["lambda_function.py"] or package.read("lambda_function.py") != (ROOT / "lambda_function.py").read_bytes():
            raise ValueError("Function ZIP must contain exactly the current handler at its root")
    fixture = ROOT / "data/input/vectors-study-55s.mp4"
    if sha256(fixture) != FIXTURE_SHA256:
        raise ValueError("Fixture checksum mismatch; the handler accepts only the retained fixture")
    return output, fixture


def aws(config, *arguments):
    environment = os.environ.copy()
    environment.update({"AWS_MAX_ATTEMPTS": "1", "AWS_RETRY_MODE": "standard", "AWS_CLI_AUTO_PROMPT": "off"})
    command = ["aws", "--profile", config["profile"], "--region", REGION,
               "--no-cli-pager", "--output", "json", *arguments]
    result = subprocess.run(command, text=True, capture_output=True, env=environment)
    if result.returncode:
        raise DeploymentError(f"AWS {' '.join(arguments[:2])} failed: {result.stderr.strip()}")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def render_policy(name, config):
    text = (ROOT / "policies" / name).read_text(encoding="utf-8")
    for old, new in {"YOUR_BUCKET": config["bucket_name"], "YOUR_PROJECT_ID": config["project_id"],
                     "YOUR_FUNCTION_NAME": config["function_name"]}.items():
        text = text.replace(old, new)
    return json.loads(text)


def deploy(config):
    output, fixture = validate_build()
    state_file = ROOT / ".local/deployment.json"
    if state_file.exists():
        raise ValueError("A deployment receipt already exists; inspect it before creating another environment")
    if shutil.which("aws") is None:
        raise ValueError("Install AWS CLI v2 and authenticate the configured profile first")
    identity = aws(config, "sts", "get-caller-identity")
    if identity.get("Account") != config["project_id"]:
        raise ValueError("Signed-in project does not match config.project_id; no resources created")
    free = aws(config, "freetier", "get-account-plan-state")
    if free.get("accountId") != config["project_id"] or free.get("accountPlanType") != "FREE" or free.get("accountPlanStatus") != "ACTIVE":
        raise ValueError("This helper requires the expected project on FREE / ACTIVE; no plan changes or resources created")

    state = {"created_at": datetime.now(timezone.utc).isoformat(), "status": "creating", "config": config,
             "created_resources": [], "inference_calls": 0, "function_invocations": 0}
    state_file.parent.mkdir(exist_ok=True)

    def save_state():
        temporary = state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(state_file)

    def created(kind, identifier):
        state["created_resources"].append({"kind": kind, "identifier": identifier})
        save_state()

    save_state()
    bucket, role, function = config["bucket_name"], config["role_name"], config["function_name"]
    log_group = "/aws/lambda/" + function
    tags = [{"Key": "Purpose", "Value": "m1-fail-fast-spike"}, {"Key": "Cleanup", "Value": "after-spike"}]
    try:
        print("Creating private Stockholm bucket and its encryption/TLS policy")
        aws(config, "s3api", "create-bucket", "--bucket", bucket,
            "--create-bucket-configuration", "LocationConstraint=" + REGION,
            "--object-ownership", "BucketOwnerEnforced")
        created("bucket", bucket)
        aws(config, "s3api", "put-public-access-block", "--bucket", bucket, "--public-access-block-configuration",
            json.dumps({k: True for k in ["BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"]}))
        aws(config, "s3api", "put-bucket-encryption", "--bucket", bucket, "--server-side-encryption-configuration",
            json.dumps({"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}))
        aws(config, "s3api", "put-bucket-policy", "--bucket", bucket, "--policy",
            json.dumps(render_policy("bucket-policy.json", config)))
        aws(config, "s3api", "put-bucket-tagging", "--bucket", bucket, "--tagging", json.dumps({"TagSet": tags}))
        print("Creating the scoped worker role and one-day log group")
        aws(config, "iam", "create-role", "--role-name", role, "--assume-role-policy-document",
            json.dumps(render_policy("lambda-trust-policy.json", config)), "--tags", json.dumps(tags))
        created("role", role)
        aws(config, "iam", "put-role-policy", "--role-name", role, "--policy-name", "M1SpikeOnly",
            "--policy-document", json.dumps(render_policy("lambda-permissions-policy.json", config)))
        created("inline_policy", role + "/M1SpikeOnly")
        aws(config, "logs", "create-log-group", "--log-group-name", log_group)
        created("log_group", log_group)
        aws(config, "logs", "put-retention-policy", "--log-group-name", log_group, "--retention-in-days", "1")
        print("Uploading the verified fixture and code packages; publishing the FFmpeg layer")
        for path, key in [(fixture, "input/vectors-study-55s.mp4"),
                          (output / "function.zip", "code/function.zip"), (output / "ffmpeg-layer.zip", "code/ffmpeg-layer.zip")]:
            aws(config, "s3api", "put-object", "--bucket", bucket, "--key", key, "--body", str(path),
                "--server-side-encryption", "AES256", "--if-none-match", "*")
            created("object", bucket + "/" + key)
        layer = aws(config, "lambda", "publish-layer-version", "--layer-name", config["layer_name"],
                    "--content", json.dumps({"S3Bucket": bucket, "S3Key": "code/ffmpeg-layer.zip"}),
                    "--compatible-runtimes", "python3.13", "--compatible-architectures", "x86_64",
                    "--license-info", "GPL-3.0-or-later")
        created("layer_version", layer["LayerVersionArn"])
        state["layer_version"] = layer["Version"]
        state["layer_version_arn"] = layer["LayerVersionArn"]
        save_state()
        print("Creating the manual-only Lambda; no Groq key, trigger, URL or invocation")
        request = {"FunctionName": function, "Runtime": "python3.13", "Architectures": ["x86_64"],
                   "Role": f"arn:aws:iam::{config['project_id']}:role/{role}", "Handler": "lambda_function.handler",
                   "Code": {"S3Bucket": bucket, "S3Key": "code/function.zip"}, "Timeout": 300,
                   "MemorySize": 1024, "EphemeralStorage": {"Size": 1024},
                   "Environment": {"Variables": {"SPIKE_BUCKET": bucket}}, "Layers": [layer["LayerVersionArn"]],
                   "Tags": {tag["Key"]: tag["Value"] for tag in tags}}
        # IAM propagation can lag. Retry only a definite role-assumption rejection.
        for attempt in range(4):
            try:
                response = aws(config, "lambda", "create-function", "--cli-input-json", json.dumps(request))
                break
            except DeploymentError as error:
                message = str(error).lower()
                if attempt == 3 or "invalidparametervalueexception" not in message or "cannot be assumed" not in message:
                    raise
                time.sleep(5)
        created("function", response["FunctionArn"])
        aws(config, "lambda", "wait", "function-active-v2", "--function-name", function)
        state["status"] = "deployed_without_groq_key"
        save_state()
        print(f"Created {function}. Receipt: {state_file}. No inference was submitted.")
    except Exception:
        state["status"] = "incomplete_inspect_receipt_and_named_resources"
        save_state()
        print(f"Deployment stopped. Inspect {state_file}; no resources were deleted automatically.", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "deploy"])
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.command == "plan":
            print(json.dumps(plan(config), indent=2))
        else:
            deploy(config)
        return 0
    except (OSError, ValueError, DeploymentError, KeyError, zipfile.BadZipFile) as error:
        print(f"Deployment helper: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
