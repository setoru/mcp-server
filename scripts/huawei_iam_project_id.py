from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

import requests
import yaml
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.sdk_request import SdkRequest

from huawei_scope import DEFAULT_SCOPE_PATH


IAM_ENDPOINT_TEMPLATE = "iam.{region}.myhuaweicloud.com"
USER_AGENT = "huaweicloud-usdk-python/3.0"
REQUEST_TIMEOUT = (60, 120)


def build_signed_iam_request(
    ak: str,
    sk: str,
    *,
    region: str,
    method: str,
    resource_path: str,
    query_params: dict[str, Any] | None = None,
) -> SdkRequest:
    endpoint = f"https://{IAM_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    url_parse_result = urlparse(endpoint)
    request = SdkRequest(
        method=method,
        schema=url_parse_result.scheme,
        host=url_parse_result.netloc,
        resource_path=resource_path,
        query_params=list((query_params or {}).items()),
        header_params={"User-Agent": USER_AGENT},
        body="",
    )
    # Sign directly. ClientBuilder would call BasicCredentials.process_auth_params(),
    # which auto-queries project_id before this tool can report the raw IAM result.
    return BasicCredentials(ak, sk).sign_request(request)


def request_json(
    *,
    ak: str,
    sk: str,
    region: str,
    method: str,
    resource_path: str,
    query_params: dict[str, Any] | None = None,
) -> Any:
    request = build_signed_iam_request(
        ak,
        sk,
        region=region,
        method=method,
        resource_path=resource_path,
        query_params=query_params or {},
    )
    response = requests.request(
        request.method,
        request.url,
        headers=request.header_params,
        data=request.body,
        timeout=REQUEST_TIMEOUT,
    )
    if not response.ok:
        detail = response.text.strip()
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(
            f"IAM request failed: HTTP {response.status_code} {response.reason}{suffix}"
        )
    return response.json() if response.content else {}


def load_scope_config(scope_path: Path) -> dict[str, Any]:
    with open(scope_path, "r", encoding="utf-8") as handle:
        scope_config = yaml.safe_load(handle) or {}
    if not isinstance(scope_config, dict):
        raise ValueError("Scope file content must be an object mapping.")
    if isinstance(scope_config.get("default"), dict):
        scope_config = scope_config["default"]
    return scope_config


def cleaned_str(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Huawei Cloud region -> project_id mapping using IAM /v3/projects?name=<region>.",
    )
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument(
        "--region",
        action="append",
        help="Region to query (repeatable). Defaults to scope region if not set.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print request parameters without sending the request.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print raw IAM response JSON per region.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Query all IAM-known regions (SDK built-in list).",
    )
    return parser


def infer_known_regions() -> list[str]:
    # Reuse the SDK's IAM endpoint region list, which should include regions that
    # have an IAM endpoint mapping.
    import huaweicloudsdkcore.auth.endpoint as endpoint_mod

    region_dict = getattr(endpoint_mod, "__IAM_ENDPOINT_DICT", None)
    if not isinstance(region_dict, dict) or not region_dict:
        raise RuntimeError(
            "Could not infer IAM regions from the SDK. Pass --region explicitly."
        )
    return sorted(str(region_id) for region_id in region_dict)


def query_projects_for_region(
    *,
    ak: str,
    sk: str,
    region: str,
) -> dict[str, Any]:
    response = request_json(
        ak=ak,
        sk=sk,
        region=region,
        method="GET",
        resource_path="/v3/projects",
        query_params={"name": region},
    )
    if not isinstance(response, dict):
        raise ValueError("Unexpected IAM response: expected an object.")
    return response


def extract_single_project_id(response: dict[str, Any]) -> str | None:
    projects = response.get("projects")
    if not isinstance(projects, list) or not projects:
        return None
    if len(projects) != 1:
        return None
    first = projects[0]
    if not isinstance(first, dict):
        return None
    return cleaned_str(first.get("id"))


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    scope_path = Path(args.scope).expanduser()
    if not scope_path.exists():
        raise FileNotFoundError(f"Scope file not found: {scope_path}")

    scope_config = load_scope_config(scope_path)
    ak = cleaned_str(scope_config.get("ak"))
    sk = cleaned_str(scope_config.get("sk"))
    if not ak or not sk:
        raise ValueError("Scope file must provide non-empty 'ak' and 'sk'.")

    scope_region = cleaned_str(scope_config.get("region"))

    regions: list[str] = []
    if args.all:
        regions = infer_known_regions()
    if args.region:
        for item in args.region:
            cleaned = cleaned_str(item)
            if cleaned:
                regions.append(cleaned)
    if not regions and scope_region:
        regions = [scope_region]
    if not regions:
        raise ValueError("No regions provided. Pass --region or set region in the scope file.")

    print("Action: query-project-id")
    print(f"Scope: {scope_path}")
    print(f"Regions: {', '.join(regions)}")

    if args.dry_run:
        print("Dry run request:")
        print(
            json.dumps(
                {
                    "endpoint_template": IAM_ENDPOINT_TEMPLATE,
                    "method": "GET",
                    "resource_path": "/v3/projects",
                    "query_params": {"name": "<region>"},
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.json_output:
        raw_results: dict[str, Any] = {}
        for region in regions:
            raw_results[region] = query_projects_for_region(
                ak=ak,
                sk=sk,
                region=region,
            )
        print(json.dumps(raw_results, indent=2, ensure_ascii=False))
        return 0

    for region in regions:
        response = query_projects_for_region(ak=ak, sk=sk, region=region)
        project_id = extract_single_project_id(response)
        if project_id:
            print(f"{region}: {project_id}")
        else:
            print(f"{region}: <not found or multiple; re-run with --json-output>")
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
