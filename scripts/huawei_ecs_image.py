from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

import yaml
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.client import Client, ClientBuilder
from huaweicloudsdkcore.exceptions.exceptions import HostUnreachableException
from huaweicloudsdkcore.region.region import Region
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.sdk_response import FutureSdkResponse
from huaweicloudsdkcore.utils import http_utils

from huawei_scope import (
    DEFAULT_LIST_LIMIT,
    DEFAULT_SCOPE_PATH,
    ECS_ENDPOINT_TEMPLATE,
    IMS_ENDPOINT_TEMPLATE,
)


class CustomClient(Client):
    def build_future_request(
        self,
        method,
        resource_path,
        path_params,
        query_params,
        header_params,
        request_body,
        post_params,
        cname,
        response_type,
        collection_formats,
        progress_callback,
    ):
        url_parse_result = self._url_parse(cname)
        schema = url_parse_result.scheme
        host = url_parse_result.netloc

        header_params = self._parse_header_params(collection_formats, header_params)
        resource_path = self._parse_path_params(
            collection_formats,
            path_params,
            resource_path,
            self._credentials.get_update_path_params(),
        )
        query_params = self._parse_query_params(collection_formats, query_params)
        post_params = self._parse_post_params(collection_formats, post_params)

        if (
            self._config.ignore_content_type_for_get_request
            and method == "GET"
            and not request_body
        ):
            header_params.pop(self._CONTENT_TYPE, None)
        else:
            content_type = header_params.setdefault(
                self._CONTENT_TYPE, self._APPLICATION_JSON
            )

            if content_type == self._MULTIPART_FORM_DATA:
                body = self._parse_form_data_body(request_body)
                header_params[self._CONTENT_TYPE] = body.content_type
            elif content_type == self._APPLICATION_X_WWW_FORM_URLENCODED:
                body = self._parse_form_urlencoded_body(request_body)
            elif content_type == self._APPLICATION_XML:
                body = self._parse_xml_body(request_body)
            elif content_type == self._APPLICATION_BSON:
                body = self._parse_bson_body(request_body)
            elif content_type == self._APPLICATION_OCTET_STREAM:
                content_length = header_params.get("content-length")
                body = self._parse_stream_body(
                    request_body, progress_callback, content_length
                )
            else:
                body = self._parse_body(request_body, post_params)

            request_body = body

        sdk_request = SdkRequest(
            method=method,
            schema=schema,
            host=host,
            resource_path=resource_path,
            query_params=query_params,
            header_params=header_params,
            body=request_body,
            stream=False,
            signing_algorithm=self._config.signing_algorithm,
        )
        return self._credentials.process_auth_request(sdk_request, self._http_client)

    def do_http_request(
        self,
        method,
        resource_path,
        path_params=None,
        query_params=None,
        header_params=None,
        body=None,
        post_params=None,
        cname=None,
        response_type=None,
        response_headers=None,
        collection_formats=None,
        request_type=None,
        async_request=False,
        progress_callback=None,
    ):
        if async_request:
            future_request = self.build_future_request(
                method,
                resource_path,
                path_params,
                query_params,
                header_params,
                body,
                post_params,
                cname,
                response_type,
                collection_formats,
                progress_callback,
            )
            future_response = self._http_client.executor.submit(
                self._do_http_request_async,
                future_request,
                response_type,
                response_headers,
                progress_callback,
            )
            return FutureSdkResponse(future_response, self._logger)

        while True:
            try:
                request = self.build_future_request(
                    method,
                    resource_path,
                    path_params,
                    query_params,
                    header_params,
                    body,
                    post_params,
                    cname,
                    response_type,
                    collection_formats,
                    progress_callback,
                ).result()
                response = self._do_http_request_sync(request)
                break
            except HostUnreachableException as exc:
                with self._mutex:
                    if self._endpoint_index < len(self._endpoints) - 1:
                        self._endpoint_index += 1
                    else:
                        self._endpoint_index = 0
                        raise exc

        return response


def create_api_client(
    ak: str,
    sk: str,
    region: str,
    *,
    endpoint_template: str,
    project_id: str | None = None,
):
    endpoint = f"https://{endpoint_template.replace('{region}', region)}"
    credentials = BasicCredentials(ak, sk, project_id) if project_id else BasicCredentials(ak, sk)
    return (
        ClientBuilder(CustomClient)
        .with_credentials(credentials)
        .with_region(Region(id=region, endpoint=endpoint))
        .build()
    )


def request_json(
    client,
    *,
    method: str,
    resource_path: str,
    query_params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = client.do_http_request(
        method=method,
        resource_path=resource_path,
        collection_formats={},
        path_params={},
        query_params=query_params or {},
        header_params={
            "Content-Type": http_utils.select_header_content_type(
                ["application/json;charset=UTF-8"]
            )
        },
        post_params={},
        body=body,
        response_headers=None,
    )
    return response.json() if response and response.content else {}


def dedupe_strings(values: Sequence[str]) -> list[str]:
    unique_values: list[str] = []
    seen_values: set[str] = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen_values:
            continue
        seen_values.add(cleaned)
        unique_values.append(cleaned)
    return unique_values


def load_scope_config(scope_path: Path) -> dict[str, Any]:
    with open(scope_path, "r", encoding="utf-8") as handle:
        scope_config = yaml.safe_load(handle) or {}
    if not isinstance(scope_config, dict):
        raise ValueError("Scope file content must be an object mapping.")
    if isinstance(scope_config.get("default"), dict):
        scope_config = scope_config["default"]
    return scope_config


def list_servers(
    client,
    *,
    project_id: str,
    name: str | None = None,
    server_id: str | None = None,
    status: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[dict[str, Any]]:
    query_params: dict[str, Any] = {"limit": limit}
    if name:
        query_params["name"] = name
    if server_id:
        query_params["server_id"] = server_id
    if status:
        query_params["status"] = status

    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v1/{project_id}/cloudservers/detail",
        query_params=query_params,
    )
    servers = response_data.get("servers", [])
    if not isinstance(servers, list):
        raise ValueError("Unexpected ECS list response: 'servers' is not a list.")
    return servers


def select_exact_name_matches(
    servers: list[dict[str, Any]],
    expected_name: str,
) -> list[dict[str, Any]]:
    matches = [
        server for server in servers if str(server.get("name", "")) == expected_name
    ]
    if not matches:
        raise ValueError(f"No ECS instance matched the exact name '{expected_name}'.")
    if len(matches) > 1:
        matched_ids = ", ".join(str(server.get("id", "")) for server in matches)
        raise ValueError(
            "Multiple ECS instances share that exact name. "
            f"Use --server-id to disambiguate. Matched IDs: {matched_ids}"
        )
    return matches


def fetch_server(
    ecs_client,
    *,
    project_id: str,
    server_id: str | None,
    name: str | None,
    limit: int,
) -> dict[str, Any]:
    if server_id:
        queried_servers = list_servers(
            ecs_client, project_id=project_id, server_id=server_id, limit=limit
        )
        exact_matches = [
            server
            for server in queried_servers
            if str(server.get("id", "")).strip() == str(server_id).strip()
        ]
        if not exact_matches:
            raise ValueError(f"Could not find ECS instance for server ID: {server_id}")
        if len(exact_matches) > 1:
            raise ValueError(
                f"Unexpected: multiple ECS instances returned for server ID: {server_id}"
            )
        return exact_matches[0]

    if name:
        queried_servers = list_servers(
            ecs_client, project_id=project_id, name=name, limit=limit
        )
        return select_exact_name_matches(queried_servers, name)[0]

    queried_servers = list_servers(ecs_client, project_id=project_id, limit=limit)
    queried_servers = [
        server for server in queried_servers if str(server.get("id", "")).strip()
    ]
    if len(queried_servers) == 1:
        return queried_servers[0]
    raise ValueError(
        "No target provided. Pass --server-id or --name, or keep only one ECS instance in the selected project for automatic targeting."
    )


def build_default_image_name(server_name: str, *, date_format: str) -> str:
    date_str = datetime.now().strftime(date_format)
    cleaned_name = server_name.strip() or "ecs"
    suffix = f"-{date_str}"
    max_len = 128
    prefix_max = max_len - len(suffix)
    if prefix_max < 1:
        return date_str[:max_len]
    if len(cleaned_name) > prefix_max:
        cleaned_name = cleaned_name[:prefix_max]
    return f"{cleaned_name}{suffix}"


@dataclass
class JobProgress:
    status: str
    current_task: str | None
    process_percent: float | None
    image_id: str | None
    image_name: str | None
    error_code: str | None
    fail_reason: str | None
    raw: dict[str, Any]


def show_job_progress(ims_client, *, job_id: str) -> JobProgress:
    response_data = request_json(
        ims_client,
        method="GET",
        resource_path=f"/v1/cloudimages/job/{job_id}",
    )
    entities = response_data.get("entities")
    if not isinstance(entities, dict):
        entities = {}

    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    return JobProgress(
        status=str(response_data.get("status", "")).strip() or "UNKNOWN",
        current_task=str(entities.get("current_task", "")).strip() or None,
        process_percent=_to_float(entities.get("process_percent")),
        image_id=str(entities.get("image_id", "")).strip() or None,
        image_name=str(entities.get("image_name", "")).strip() or None,
        error_code=str(response_data.get("error_code", "")).strip() or None,
        fail_reason=str(response_data.get("fail_reason", "")).strip() or None,
        raw=response_data,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a Huawei Cloud IMS private image from an ECS server (image name defaults to <server_name>-<date>).",
    )
    parser.add_argument("action", choices=("create",))
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument("--region", help="Override the region from the scope file.")
    parser.add_argument(
        "--project-id",
        dest="project_id",
        help="Override the project_id from the scope file (used for ECS lookup).",
    )
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--server-id",
        dest="server_id",
        help="Target ECS server id (recommended).",
    )
    target_group.add_argument(
        "--name",
        help="Target ECS server name (must be an exact match).",
    )
    parser.add_argument(
        "--image-name",
        dest="image_name",
        help="Override the generated image name.",
    )
    parser.add_argument(
        "--date-format",
        dest="date_format",
        default="%Y%m%d",
        help="strftime format for the date suffix (default: %%Y%%m%%d).",
    )
    parser.add_argument(
        "--description",
        help="Image description (optional).",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Image tag (repeatable).",
    )
    parser.add_argument(
        "--enterprise-project-id",
        dest="enterprise_project_id",
        help="Enterprise project id for the created image (optional).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help="Maximum number of ECS instances to query when selecting by name or auto mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print request body without sending the request.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll IMS job progress until SUCCESS/FAIL.",
    )
    parser.add_argument(
        "--poll-interval",
        dest="poll_interval",
        type=float,
        default=10.0,
        help="Seconds between job status polls when --wait is set (default: 10).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3600.0,
        help="Max seconds to wait for job completion when --wait is set (default: 3600).",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full job progress responses as JSON when --wait is set.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    scope_path = Path(args.scope).expanduser()
    if not scope_path.exists():
        raise FileNotFoundError(f"Scope file not found: {scope_path}")

    scope_config = load_scope_config(scope_path)
    ak = str(scope_config.get("ak", "")).strip()
    sk = str(scope_config.get("sk", "")).strip()
    if not ak or not sk:
        raise ValueError("Scope file must provide non-empty 'ak' and 'sk'.")

    region = args.region or str(scope_config.get("region", "")).strip() or None
    project_id = (
        args.project_id or str(scope_config.get("project_id", "")).strip() or None
    )
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")
    if not project_id:
        raise ValueError(
            "Missing project_id. Set it in the scope file or pass --project-id."
        )
    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    ecs_client = create_api_client(
        ak,
        sk,
        region,
        endpoint_template=ECS_ENDPOINT_TEMPLATE,
        project_id=project_id,
    )
    server = fetch_server(
        ecs_client,
        project_id=project_id,
        server_id=args.server_id,
        name=args.name,
        limit=args.limit,
    )
    server_id = str(server.get("id", "")).strip()
    server_name = str(server.get("name", "")).strip()
    server_status = str(server.get("status", "UNKNOWN")).strip() or "UNKNOWN"
    if not server_id:
        raise ValueError("Unexpected ECS response: server id is empty.")

    image_name = args.image_name or build_default_image_name(
        server_name or server_id, date_format=args.date_format
    )
    description = args.description
    if description is None:
        description = f"Created from ECS '{server_name or server_id}' at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    request_body: dict[str, Any] = {
        "name": image_name,
        "instance_id": server_id,
        "description": description,
    }
    tags = dedupe_strings(args.tag)
    if tags:
        request_body["tags"] = tags
    if args.enterprise_project_id:
        request_body["enterprise_project_id"] = args.enterprise_project_id

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print(f"Target ECS: {server_name or '<unknown>'} ({server_id}) status={server_status}")
    print(f"Image Name: {image_name}")
    if server_status.upper() != "SHUTOFF":
        print(
            "Warning: ECS is not in SHUTOFF state. Creating an image from a running instance may be inconsistent or rejected by the API.",
            file=sys.stderr,
        )

    if args.dry_run:
        print("Dry run request:")
        print(json.dumps(request_body, indent=2, ensure_ascii=False))
        return 0

    ims_client = create_api_client(
        ak,
        sk,
        region,
        endpoint_template=IMS_ENDPOINT_TEMPLATE,
        project_id=project_id,
    )
    response_data = request_json(
        ims_client,
        method="POST",
        resource_path="/v2/cloudimages/action",
        body=request_body,
    )
    job_id = str(response_data.get("job_id", "")).strip()
    print("Response:")
    print(json.dumps(response_data, indent=2, ensure_ascii=False))
    if not job_id:
        raise ValueError("Unexpected IMS response: missing job_id.")

    if not args.wait:
        return 0

    if args.poll_interval <= 0:
        raise ValueError("--poll-interval must be greater than 0.")
    if args.timeout <= 0:
        raise ValueError("--timeout must be greater than 0.")

    deadline = time.time() + float(args.timeout)
    while True:
        progress = show_job_progress(ims_client, job_id=job_id)
        if args.json_output:
            print(json.dumps(progress.raw, indent=2, ensure_ascii=False))
        else:
            percent = (
                f"{progress.process_percent:.1f}%" if progress.process_percent is not None else "-"
            )
            task = progress.current_task or "-"
            print(f"Job: {job_id} status={progress.status} progress={percent} task={task}")

        if progress.status in ("SUCCESS", "FAIL"):
            if progress.status == "SUCCESS":
                if progress.image_id:
                    print(f"Image ID: {progress.image_id}")
                if progress.image_name:
                    print(f"Image Name: {progress.image_name}")
                return 0

            fail_reason = progress.fail_reason or "-"
            error_code = progress.error_code or "-"
            print(f"Job failed: error_code={error_code} reason={fail_reason}", file=sys.stderr)
            return 1

        if time.time() >= deadline:
            raise TimeoutError(
                f"Timed out after {args.timeout:.0f}s waiting for job {job_id}."
            )

        time.sleep(float(args.poll_interval))


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
