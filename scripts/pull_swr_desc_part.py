from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


def parse_part_number(value: str) -> int:
    if not re.fullmatch(r"\d+", value):
        raise ValueError(f"Part number must be a positive integer, got: {value}")

    number = int(value)
    if number < 1:
        raise ValueError(f"Part number must be greater than 0, got: {value}")
    return number


def resolve_inputs(argv: Sequence[str]) -> tuple[int, str | None]:
    if not argv:
        raise ValueError(
            "Usage: pull-swr-desc-part.cmd <part-number> [merge-dir]\n"
            "   or: pull-swr-desc-part.cmd [merge-dir] <part-number>"
        )

    if len(argv) > 2:
        raise ValueError(
            "Expected 1 or 2 arguments before any export overrides. "
            "Use the .cmd config for a fixed merge dir, or pass merge dir plus part number."
        )

    part_number: int | None = None
    merge_dir: str | None = None

    for value in argv:
        try:
            parsed_part = parse_part_number(value)
        except ValueError:
            if merge_dir is not None:
                raise ValueError(f"Merge directory was provided more than once: {argv}")
            merge_dir = value
        else:
            if part_number is not None:
                raise ValueError(f"Part number was provided more than once: {argv}")
            part_number = parsed_part

    if part_number is None:
        raise ValueError(
            "Missing part number. Example: pull-swr-desc-part.cmd 3 C:\\SWRDescriptionExports\\merge_photo"
        )

    return part_number, merge_dir


def run(argv: Sequence[str] | None = None) -> int:
    raw_args = list(argv if argv is not None else sys.argv[1:])
    part_number, merge_dir_arg = resolve_inputs(raw_args)

    configured_value = os.environ.get("CONFIG_MERGE_DIR") or None
    merge_dir_value = merge_dir_arg or configured_value

    if not merge_dir_value:
        raise ValueError(
            "Merge directory is required. Set CONFIG_MERGE_DIR at the top of pull-swr-desc-part.cmd, "
            "or pass it as an argument."
        )

    merge_dir = Path(merge_dir_value).expanduser()
    merge_dir.mkdir(parents=True, exist_ok=True)

    script_dir = Path(__file__).resolve().parent
    export_script = script_dir / "export_swr_repo_desc.py"
    if not export_script.exists():
        raise FileNotFoundError(f"export_swr_repo_desc.py not found: {export_script}")

    temp_dir_path = Path(tempfile.mkdtemp(prefix=f"swr-desc-part-{part_number:04d}-"))

    try:
        command = [
            sys.executable,
            str(export_script),
            "--output-dir",
            str(temp_dir_path),
        ]
        completed = subprocess.run(
            command,
            cwd=str(script_dir.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if completed.stdout:
            print(completed.stdout.rstrip())
        if completed.returncode != 0:
            if completed.stderr:
                print(completed.stderr.rstrip(), file=sys.stderr)
            raise RuntimeError(f"Export command failed with exit code {completed.returncode}.")

        part_files = sorted(temp_dir_path.glob("description.part*.txt"))
        if len(part_files) != 1:
            raise ValueError(
                f"Expected exactly 1 exported description part, found {len(part_files)} in {temp_dir_path}"
            )

        source_part = part_files[0]
        target_part = merge_dir / f"description.part{part_number:04d}.txt"
        shutil.copy2(source_part, target_part)

        print(f"Saved part {part_number:04d} to: {target_part}")
        return 0

    finally:
        shutil.rmtree(temp_dir_path, ignore_errors=True)


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
