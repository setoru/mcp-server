from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


DEFAULT_NAMESPACE = "huaweicloud"
DEFAULT_REPOSITORY = "cce/kruise-game-manager"
DEFAULT_CHUNK_SIZE = 30000
DEFAULT_EXPORT_ROOT = Path("C:/SWRDescriptionExports")


def safe_path_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return safe.strip("._-") or "value"


def default_output_dir(namespace: str, repository: str) -> Path:
    current_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    name = f"{current_timestamp}__{safe_path_name(namespace)}__{safe_path_name(repository)}"
    return DEFAULT_EXPORT_ROOT / name


def extract_json_object(output: str) -> dict[str, Any]:
    start = output.find("{")
    end = output.rfind("}")

    if start < 0 or end < start:
        raise ValueError("show-swr-repo output did not contain a JSON object.")

    payload = output[start : end + 1]
    parsed = json.loads(payload)

    if not isinstance(parsed, dict):
        raise ValueError("show-swr-repo JSON output was not an object.")

    return parsed


def run_show_repo(
    *,
    script_dir: Path,
    namespace: str,
    repository: str,
    scope: str | None,
    region: str | None,
    project_id: str | None,
) -> dict[str, Any]:
    show_cmd = script_dir / "show-swr-repo.cmd"

    if not show_cmd.exists():
        raise FileNotFoundError(f"show-swr-repo.cmd not found: {show_cmd}")

    command = [
        str(show_cmd),
        "--namespace",
        namespace,
        "--repository",
        repository,
        "--json-output",
    ]

    if scope:
        command.extend(["--scope", scope])
    if region:
        command.extend(["--region", region])
    if project_id:
        command.extend(["--project-id", project_id])

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    completed = subprocess.run(
        command,
        cwd=str(script_dir.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    if completed.returncode != 0:
        message = [
            f"show-swr-repo failed with exit code {completed.returncode}.",
            "Command:",
            " ".join(command),
        ]
        if completed.stdout.strip():
            message.extend(["STDOUT:", completed.stdout.rstrip()])
        if completed.stderr.strip():
            message.extend(["STDERR:", completed.stderr.rstrip()])
        raise RuntimeError("\n".join(message))

    return extract_json_object(completed.stdout)


def write_description_parts(
    *,
    description: str,
    output_dir: Path,
    chunk_size: int,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    for old_part in output_dir.glob("description.part*.txt"):
        old_part.unlink()
    for old_file_name in ("description.txt", "manifest.json", "repo.json"):
        old_file = output_dir / old_file_name
        if old_file.exists():
            old_file.unlink()

    if not description:
        chunks = [""]
    else:
        chunks = [
            description[index : index + chunk_size]
            for index in range(0, len(description), chunk_size)
        ]

    part_paths: list[Path] = []
    for index, chunk in enumerate(chunks, start=1):
        part_path = output_dir / f"description.part{index:04d}.txt"
        with open(part_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(chunk)
        part_paths.append(part_path)

    if len(part_paths) == 1:
        single_path = output_dir / "description.txt"
        with open(single_path, "w", encoding="utf-8", newline="") as handle:
            handle.write(description)

    return part_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export the Description field returned by scripts\\show-swr-repo.cmd "
            "and split it into files of at most 30000 characters by default."
        )
    )
    parser.add_argument(
        "--namespace",
        default=DEFAULT_NAMESPACE,
        help=f"SWR namespace. Default: {DEFAULT_NAMESPACE}",
    )
    parser.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
        help=f"SWR repository. Default: {DEFAULT_REPOSITORY}",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory for exported description files. Default: C:\\SWRDescriptionExports\\<YYYY-MM-DD_HH-MM>__<namespace>__<repository>",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Maximum characters per output file. Default: {DEFAULT_CHUNK_SIZE}",
    )
    parser.add_argument("--scope", help="Pass through to show-swr-repo.cmd.")
    parser.add_argument("--region", help="Pass through to show-swr-repo.cmd.")
    parser.add_argument("--project-id", help="Pass through to show-swr-repo.cmd.")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.chunk_size < 1:
        raise ValueError("--chunk-size must be greater than 0.")

    namespace = str(args.namespace).strip()
    repository = str(args.repository).strip()
    if not namespace:
        raise ValueError("--namespace must not be empty.")
    if not repository:
        raise ValueError("--repository must not be empty.")

    script_dir = Path(__file__).resolve().parent
    output_dir = (
        Path(args.output_dir).expanduser()
        if args.output_dir
        else default_output_dir(namespace, repository)
    )

    repo = run_show_repo(
        script_dir=script_dir,
        namespace=namespace,
        repository=repository,
        scope=args.scope,
        region=args.region,
        project_id=args.project_id,
    )

    raw_description = repo.get("description")
    description = "" if raw_description is None else str(raw_description)

    part_paths = write_description_parts(
        description=description,
        output_dir=output_dir,
        chunk_size=args.chunk_size,
    )

    with open(output_dir / "repo.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(repo, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    manifest = {
        "tool": "export_swr_repo_desc",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "namespace": namespace,
        "repository": repository,
        "description_characters": len(description),
        "chunk_size": args.chunk_size,
        "part_count": len(part_paths),
        "part_files": [path.name for path in part_paths],
        "single_file": "description.txt" if len(part_paths) == 1 else None,
        "source_command": [
            "scripts\\show-swr-repo.cmd",
            "--namespace",
            namespace,
            "--repository",
            repository,
            "--json-output",
        ],
    }
    with open(output_dir / "manifest.json", "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Repository: {namespace}/{repository}")
    print(f"Output directory: {output_dir}")
    print(f"Description characters: {len(description)}")
    print(f"Chunk size: {args.chunk_size}")
    print(f"Files created: {len(part_paths)}")
    for path in part_paths:
        print(f"  {path}")
    if len(part_paths) == 1:
        print(f"Single-file copy: {output_dir / 'description.txt'}")
    print(f"Manifest: {output_dir / 'manifest.json'}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
