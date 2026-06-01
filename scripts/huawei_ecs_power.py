from __future__ import annotations

import argparse
import json
import sys
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

from huawei_scope import DEFAULT_SCOPE_PATH


ECS_ENDPOINT_TEMPLATE = "ecs.{region}.myhuaweicloud.com"
DEFAULT_LIST_LIMIT = 1000


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
            content_type = header_params.pop(self._CONTENT_TYPE, None)
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

        sdk_request = SdkRequest(
            method=method,
            schema=schema,
            host=host,
            resource_path=resource_path,
            query_params=query_params,
            header_params=header_params,
            body=body,
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


def create_api_client(ak: str, sk: str, region: str, *, project_id: str | None = None):
    endpoint = f"https://{ECS_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    credentials = BasicCredentials(ak, sk, project_id) if project_id else BasicCredentials(ak, sk)
    return (
        ClientBuilder(CustomClient)
        .with_credentials(credentials)
        .with_region(Region(id=region, endpoint=endpoint))
        .build()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List, start, or stop Huawei Cloud ECS instances with a standalone script.",
    )
    parser.add_argument("action", choices=("list", "start", "stop"))
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument("--region", help="Override the region from the scope file.")
    parser.add_argument(
        "--project-id",
        help="Override the project_id from the scope file.",
    )
    parser.add_argument(
        "--stop-type",
        choices=("SOFT", "HARD"),
        help="Stop type for stop actions. Defaults to SOFT or ecs_stop.type in scope.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve targets and print the request without sending it.",
    )
    parser.add_argument(
        "--status",
        help="Filter ECS list by status, for example ACTIVE or SHUTOFF.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help="Maximum number of ECS records to query. Default is 1000.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full ECS list results as JSON.",
    )
    parser.add_argument(
        "--all-name-matches",
        action="store_true",
        help="Allow multiple exact matches when selecting by --name.",
    )

    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--server-id",
        dest="server_ids",
        action="append",
        help="Target ECS server ID. Repeat or use comma-separated values.",
    )
    target_group.add_argument(
        "--name",
        help="Exact ECS name to match.",
    )
    return parser


def load_scope_config(scope_path: Path) -> dict[str, Any]:
    with open(scope_path, "r", encoding="utf-8") as handle:
        scope_config = yaml.safe_load(handle) or {}
    if not isinstance(scope_config, dict):
        raise ValueError("Scope file content must be an object mapping.")
    if isinstance(scope_config.get("default"), dict):
        scope_config = scope_config["default"]
    return scope_config


def parse_server_id_args(raw_values: Sequence[str] | None) -> list[str]:
    server_ids: list[str] = []
    for raw_value in raw_values or []:
        for part in str(raw_value).split(","):
            server_id = part.strip()
            if server_id:
                server_ids.append(server_id)
    return dedupe_strings(server_ids)


def normalize_server_ids(server_refs: Any) -> list[str]:
    if server_refs in (None, ""):
        return []
    if not isinstance(server_refs, list):
        raise ValueError("Scope 'servers' must be a list.")

    server_ids: list[str] = []
    for item in server_refs:
        if isinstance(item, str):
            server_id = item.strip()
        elif isinstance(item, dict):
            server_id = str(item.get("id", "")).strip()
        else:
            raise ValueError("Each scope server entry must be a string or an object with an 'id' field.")

        if not server_id:
            raise ValueError("Scope server entries must include a non-empty id.")
        server_ids.append(server_id)

    return dedupe_strings(server_ids)


def resolve_action_defaults(scope_config: dict[str, Any], action: str) -> dict[str, Any]:
    section_name = f"ecs_{action}"
    section = scope_config.get(section_name) or {}
    if not isinstance(section, dict):
        raise ValueError(f"Scope section '{section_name}' must be an object.")

    defaults = {
        "region": section.get("region") or scope_config.get("region"),
        "project_id": section.get("project_id") or scope_config.get("project_id"),
        "servers": normalize_server_ids(section.get("servers")),
    }
    if action == "stop":
        defaults["type"] = str(section.get("type") or "SOFT").upper()
    return defaults


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


def dedupe_servers(servers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_servers: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for server in servers:
        server_id = str(server.get("id", "")).strip()
        if not server_id or server_id in seen_ids:
            continue
        seen_ids.add(server_id)
        unique_servers.append(server)
    return unique_servers


def select_exact_name_matches(
    servers: list[dict[str, Any]],
    expected_name: str,
    allow_multiple: bool = False,
) -> list[dict[str, Any]]:
    matches = [
        server for server in servers if str(server.get("name", "")) == expected_name
    ]
    if not matches:
        raise ValueError(f"No ECS instance matched the exact name '{expected_name}'.")
    if len(matches) > 1 and not allow_multiple:
        matched_ids = ", ".join(str(server.get("id", "")) for server in matches)
        raise ValueError(
            "Multiple ECS instances share that exact name. "
            f"Use --server-id to disambiguate or pass --all-name-matches. Matched IDs: {matched_ids}"
        )
    return dedupe_servers(matches)


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


def fetch_servers_by_ids(
    client,
    *,
    project_id: str,
    server_ids: Sequence[str],
) -> list[dict[str, Any]]:
    resolved_servers: list[dict[str, Any]] = []
    missing_server_ids: list[str] = []
    for server_id in dedupe_strings(server_ids):
        queried_servers = list_servers(
            client,
            project_id=project_id,
            server_id=server_id,
        )
        exact_matches = [
            server for server in queried_servers if str(server.get("id", "")) == server_id
        ]
        if not exact_matches:
            missing_server_ids.append(server_id)
            continue
        resolved_servers.extend(exact_matches)

    if missing_server_ids:
        missing = ", ".join(missing_server_ids)
        raise ValueError(f"Could not find ECS instances for server IDs: {missing}")
    return dedupe_servers(resolved_servers)


def batch_start(client, *, project_id: str, server_ids: Sequence[str]) -> dict[str, Any]:
    return request_json(
        client,
        method="POST",
        resource_path=f"/v1/{project_id}/cloudservers/action",
        body={
            "os-start": {
                "servers": [{"id": server_id} for server_id in dedupe_strings(server_ids)]
            }
        },
    )


def batch_stop(
    client,
    *,
    project_id: str,
    server_ids: Sequence[str],
    stop_type: str,
) -> dict[str, Any]:
    return request_json(
        client,
        method="POST",
        resource_path=f"/v1/{project_id}/cloudservers/action",
        body={
            "os-stop": {
                "servers": [{"id": server_id} for server_id in dedupe_strings(server_ids)],
                "type": stop_type,
            }
        },
    )


def format_addresses(server: dict[str, Any]) -> str:
    addresses = server.get("addresses", {})
    if not isinstance(addresses, dict):
        return "-"

    ip_values: list[str] = []
    for network_items in addresses.values():
        if not isinstance(network_items, list):
            continue
        for item in network_items:
            if not isinstance(item, dict):
                continue
            addr = str(item.get("addr", "")).strip()
            if addr:
                ip_values.append(addr)
    deduped = dedupe_strings(ip_values)
    return ", ".join(deduped) if deduped else "-"


def print_server_list(servers: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(servers, indent=2, ensure_ascii=False))
        return

    if not servers:
        print("No ECS instances found.")
        return

    for index, server in enumerate(servers, start=1):
        print(
            f"{index}. {server.get('name', '<unknown>')} | "
            f"id={server.get('id', '')} | "
            f"status={server.get('status', 'UNKNOWN')} | "
            f"flavor={server.get('flavor', {}).get('id', '-') if isinstance(server.get('flavor'), dict) else '-'} | "
            f"ips={format_addresses(server)}"
        )


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

    action_defaults = resolve_action_defaults(scope_config, args.action)
    region = args.region or action_defaults.get("region")
    project_id = args.project_id or action_defaults.get("project_id")
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")
    if not project_id:
        raise ValueError("Missing project_id. Set it in the scope file or pass --project-id.")

    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    requested_server_ids = parse_server_id_args(args.server_ids)
    scope_server_ids = action_defaults.get("servers") or []
    client = create_api_client(ak, sk, region, project_id=project_id)

    if args.action == "list":
        queried_servers = dedupe_servers(
            list_servers(
                client,
                project_id=project_id,
                name=args.name,
                server_id=requested_server_ids[0] if len(requested_server_ids) == 1 else None,
                status=args.status,
                limit=args.limit,
            )
        )
        if requested_server_ids and len(requested_server_ids) > 1:
            queried_servers = fetch_servers_by_ids(
                client,
                project_id=project_id,
                server_ids=requested_server_ids,
            )

        print(f"Action: {args.action}")
        print(f"Scope: {scope_path}")
        print(f"Region: {region}")
        print(f"Project ID: {project_id}")
        print(f"ECS Count: {len(queried_servers)}")
        print_server_list(queried_servers, as_json=args.json_output)
        return 0

    if requested_server_ids:
        target_servers = fetch_servers_by_ids(
            client,
            project_id=project_id,
            server_ids=requested_server_ids,
        )
    elif args.name:
        queried_servers = list_servers(
            client,
            project_id=project_id,
            name=args.name,
            limit=args.limit,
        )
        target_servers = select_exact_name_matches(
            queried_servers,
            args.name,
            allow_multiple=args.all_name_matches,
        )
    elif scope_server_ids:
        target_servers = fetch_servers_by_ids(
            client,
            project_id=project_id,
            server_ids=scope_server_ids,
        )
    else:
        queried_servers = dedupe_servers(
            list_servers(
                client,
                project_id=project_id,
                limit=args.limit,
            )
        )
        if len(queried_servers) == 1:
            target_servers = queried_servers
        else:
            raise ValueError(
                "No targets provided. Pass --server-id or --name, configure ecs_start/ecs_stop.servers in the scope file, "
                "or keep only one ECS instance in the selected project for automatic targeting."
            )

    target_server_ids = [str(server["id"]) for server in target_servers]
    stop_type = args.stop_type or action_defaults.get("type") or "SOFT"

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print("Targets:")
    for server in target_servers:
        name = str(server.get("name", "<unknown>"))
        server_id = str(server.get("id", ""))
        status = str(server.get("status", "UNKNOWN"))
        print(f"  - {name} ({server_id}) status={status}")

    if args.dry_run:
        request_body = {"servers": [{"id": server_id} for server_id in target_server_ids]}
        if args.action == "stop":
            request_body["type"] = stop_type
        print("Dry run request:")
        print(json.dumps(request_body, indent=2, ensure_ascii=False))
        return 0

    if args.action == "start":
        response_data = batch_start(
            client,
            project_id=project_id,
            server_ids=target_server_ids,
        )
    else:
        response_data = batch_stop(
            client,
            project_id=project_id,
            server_ids=target_server_ids,
            stop_type=stop_type,
        )

    print("Response:")
    print(json.dumps(response_data, indent=2, ensure_ascii=False))
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
