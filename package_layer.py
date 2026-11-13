"""Build portable Lambda/FFmpeg ZIPs locally; no AWS or inference calls."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
WHEEL_SHA256 = "050d6850601c3b3890bd2b28306f3b842b3daea390a561101174375a1c460bda"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_entry(archive, name, data, mode):
    info = zipfile.ZipInfo(name, date_time=(2026, 11, 7, 0, 0, 0))
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | mode) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def build(wheel_path, output_dir):
    wheel_path, output_dir = Path(wheel_path), Path(output_dir)
    wheel_bytes = wheel_path.read_bytes()
    if sha256(wheel_bytes) != WHEEL_SHA256:
        raise ValueError("FFmpeg wheel checksum mismatch; no package was written")
    function = (ROOT / "lambda_function.py").read_bytes()
    ast.parse(function.decode("utf-8"))
    with zipfile.ZipFile(wheel_path) as source:
        names = [n for n in source.namelist() if "/binaries/ffmpeg-linux-x86_64-" in n]
        if len(names) != 1:
            raise ValueError("Expected exactly one Linux x86_64 FFmpeg executable")
        binary = source.read(names[0])
    metadata = {
        "wheel": wheel_path.name, "wheel_sha256": WHEEL_SHA256,
        "wheel_source": "https://pypi.org/project/imageio-ffmpeg/0.8.1/#files",
        "upstream_manifest": "https://github.com/imageio/imageio-ffmpeg/blob/v0.8.1/tools/ffmpeg-sources.json",
        "binary_name": names[0], "binary_bytes": len(binary), "binary_sha256": sha256(binary),
        "build": "BtbN static FFmpeg libraries; runtime glibc >= 2.28",
        "license": "FFmpeg GPL v3 or later (--enable-gpl --enable-version3); verify -L in Lambda",
        "license_url": "https://github.com/FFmpeg/FFmpeg/blob/master/COPYING.GPLv3",
        "function_source_sha256": sha256(function),
    }
    notice = json.dumps(metadata, indent=2).encode()
    combined = len(function) + len(binary) + len(notice)
    if combined >= 250 * 1024 * 1024:
        raise ValueError("Combined function/layer package exceeds the packaging ceiling")
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_dir / "function.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        write_entry(archive, "lambda_function.py", function, 0o644)
    with zipfile.ZipFile(output_dir / "ffmpeg-layer.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        write_entry(archive, "bin/ffmpeg", binary, 0o755)
        write_entry(archive, "share/doc/ffmpeg-source.json", notice, 0o644)
    metadata.update({
        "combined_unzipped_bytes": combined,
        "function_zip_sha256": sha256((output_dir / "function.zip").read_bytes()),
        "layer_zip_sha256": sha256((output_dir / "ffmpeg-layer.zip").read_bytes()),
    })
    (output_dir / "layer-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, help="Path to the pinned Linux imageio-ffmpeg wheel")
    parser.add_argument("--download-wheel", action="store_true", help="Download the pinned public wheel with pip; no installation")
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".build")
    args = parser.parse_args()
    cache = ROOT / ".local/wheels"
    if args.wheel and args.download_wheel:
        parser.error("Choose --wheel or --download-wheel")
    try:
        if args.download_wheel:
            cache.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "--only-binary=:all:",
                            "--platform", "manylinux_2_28_x86_64", "--dest", str(cache),
                            "--retries", "0", "--timeout", "30", "imageio-ffmpeg==0.8.1"], check=True)
        wheel = args.wheel
        if wheel is None:
            candidates = list(cache.glob("imageio_ffmpeg-0.8.1-*.whl"))
            if len(candidates) != 1:
                parser.error("Supply --wheel PATH or use --download-wheel")
            wheel = candidates[0]
        metadata = build(wheel, args.output_dir)
        print(json.dumps({"output_dir": str(args.output_dir.resolve()), **metadata}, indent=2))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(f"Package build failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
