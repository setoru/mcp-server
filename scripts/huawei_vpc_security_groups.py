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

from huawei_scope import (
    DEFAULT_LIST_LIMIT_VPC,
    DEFAULT_SCOPE_PATH,
    VPC_ENDPOINT_TEMPLATE,
    VPC_SECURITY_GROUPS_SECTION,
)


DEFAULT_LIST_LIMIT = DEFAULT_LIST_LIMIT_VPC
SCOPE_SECTION = VPC_SECURITY_GROUPS_SECTION


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


def create_api_client(ak: str, sk: str, region: str):
    endpoint = f"https://{VPC_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    return (
        ClientBuilder(CustomClient)
        .with_credentials(BasicCredentials(ak, sk))
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


def split_csv_values(values: Sequence[str] | None) -> list[str]:
    items: list[str] = []
    for raw_value in values or []:
        for value in str(raw_value).split(","):
            cleaned = value.strip()
            if cleaned:
                items.append(cleaned)
    return items


def resolve_action_defaults(scope_config: dict[str, Any]) -> dict[str, Any]:
    section = scope_config.get(SCOPE_SECTION) or {}
    if not isinstance(section, dict):
        raise ValueError(f"Scope section '{SCOPE_SECTION}' must be an object.")
    return {
        "region": section.get("region") or scope_config.get("region"),
        "project_id": section.get("project_id") or scope_config.get("project_id"),
        "limit": section.get("limit"),
        "marker": section.get("marker"),
        "id": section.get("id"),
        "name": section.get("name"),
        "description": section.get("description"),
        "enterprise_project_id": section.get("enterprise_project_id")
        or scope_config.get("enterprise_project_id"),
        "security_group_id": section.get("security_group_id"),
    }


def list_security_groups(
    client,
    *,
    project_id: str,
    query_params: dict[str, Any],
) -> list[dict[str, Any]]:
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v3/{project_id}/security-groups",
        query_params=query_params,
    )
    groups = response_data.get("security_groups", [])
    if not isinstance(groups, list):
        raise ValueError(
            "Unexpected security-group list response: 'security_groups' is not a list."
        )
    return groups


def show_security_group(
    client,
    *,
    project_id: str,
    security_group_id: str,
) -> dict[str, Any]:
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v3/{project_id}/security-groups/{security_group_id}",
    )
    return response_data.get("security_group", response_data)


def summarize_rule(rule: dict[str, Any]) -> str:
    if not isinstance(rule, dict):
        return "-"
    direction = cleaned_str(rule.get("direction")) or "-"
    protocol = cleaned_str(rule.get("protocol")) or "any"
    multiport = cleaned_str(rule.get("multiport")) or cleaned_str(rule.get("port_range_min")) or "-"
    ether = cleaned_str(rule.get("ethertype")) or "-"
    action = cleaned_str(rule.get("action")) or "-"
    peer = (
        cleaned_str(rule.get("remote_ip_prefix"))
        or cleaned_str(rule.get("remote_group_id"))
        or cleaned_str(rule.get("remote_address_group_id"))
        or "-"
    )
    return f"{direction}/{ether}/{protocol}:{multiport} {action} <- {peer}"


def print_security_groups(groups: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(groups, indent=2, ensure_ascii=False))
        return

    if not groups:
        print("No security groups found.")
        return

    for index, group in enumerate(groups, start=1):
        group_id = cleaned_str(group.get("id")) or "-"
        name = cleaned_str(group.get("name")) or "-"
        description = cleaned_str(group.get("description")) or "-"
        vpc_id = cleaned_str(group.get("vpc_id")) or "-"
        print(f"{index}. {name} | id={group_id} | vpc={vpc_id} | desc={description}")
        ingress_rules = group.get("ingress_rules") or []
        egress_rules = group.get("egress_rules") or []
        for rule in ingress_rules:
            print(f"   ingress: {summarize_rule(rule)}")
        for rule in egress_rules:
            print(f"   egress:  {summarize_rule(rule)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Huawei Cloud VPC security groups with a standalone script.",
    )
    parser.add_argument("action", choices=("list", "show"))
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument("--region", help="Override the region from the scope file.")
    parser.add_argument(
        "--project-id",
        dest="project_id",
        help="Override the project_id from the scope file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help=f"Maximum number of security groups to query. Default is {DEFAULT_LIST_LIMIT}.",
    )
    parser.add_argument("--marker", help="Pagination marker (security group ID).")
    parser.add_argument("--id", help="Filter by exact security group ID.")
    parser.add_argument("--name", help="Filter by exact security group name.")
    parser.add_argument("--description", help="Filter by description substring.")
    parser.add_argument(
        "--enterprise-project-id",
        dest="enterprise_project_id",
        help="Filter by enterprise project ID.",
    )
    parser.add_argument(
        "--security-group-id",
        dest="security_group_id",
        help="Target security group ID for the 'show' action.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full results as JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved request and exit without sending it.",
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

    action_defaults = resolve_action_defaults(scope_config)
    region = args.region or cleaned_str(action_defaults.get("region"))
    project_id = args.project_id or cleaned_str(action_defaults.get("project_id"))
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")
    if not project_id:
        raise ValueError("Missing project_id. Set it in the scope file or pass --project-id.")
    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    security_group_id = (
        args.security_group_id or cleaned_str(action_defaults.get("security_group_id"))
    )

    if args.action == "show":
        if not security_group_id:
            raise ValueError(
                "Show requires a security group ID. Pass --security-group-id or set "
                f"{SCOPE_SECTION}.security_group_id."
            )
        resource_path = f"/v3/{project_id}/security-groups/{security_group_id}"
        print(f"Action: {args.action}")
        print(f"Scope: {scope_path}")
        print(f"Region: {region}")
        print(f"Project ID: {project_id}")
        if args.dry_run:
            print("Dry run request:")
            print(
                json.dumps(
                    {"method": "GET", "resource_path": resource_path},
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0

        client = create_api_client(ak, sk, region)
        group = show_security_group(
            client, project_id=project_id, security_group_id=security_group_id
        )
        print("Security Group:")
        print(json.dumps(group, indent=2, ensure_ascii=False))
        return 0

    query_params: dict[str, Any] = {"limit": args.limit}
    marker = args.marker or cleaned_str(action_defaults.get("marker"))
    if marker:
        query_params["marker"] = marker
    id_filter = args.id or cleaned_str(action_defaults.get("id"))
    if id_filter:
        query_params["id"] = id_filter
    name = args.name or cleaned_str(action_defaults.get("name"))
    if name:
        query_params["name"] = name
    description = args.description or cleaned_str(action_defaults.get("description"))
    if description:
        query_params["description"] = description
    enterprise_project_id = args.enterprise_project_id or cleaned_str(
        action_defaults.get("enterprise_project_id")
    )
    if enterprise_project_id:
        query_params["enterprise_project_id"] = enterprise_project_id

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    if args.dry_run:
        print("Dry run query params:")
        print(json.dumps(query_params, indent=2, ensure_ascii=False))
        return 0

    client = create_api_client(ak, sk, region)
    groups = list_security_groups(
        client, project_id=project_id, query_params=query_params
    )
    print(f"Security Group Count: {len(groups)}")
    print_security_groups(groups, as_json=args.json_output)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {type(exc).__name__} - {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
