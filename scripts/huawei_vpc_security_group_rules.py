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
    VPC_SECURITY_GROUP_RULES_SECTION,
)


DEFAULT_LIST_LIMIT = DEFAULT_LIST_LIMIT_VPC
SCOPE_SECTION = VPC_SECURITY_GROUP_RULES_SECTION
VALID_DIRECTIONS = {"ingress", "egress"}
VALID_ETHERTYPES = {"IPv4", "IPv6"}
VALID_ACTIONS = {"allow", "deny"}


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


def normalize_scope_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    cleaned = str(value).strip().lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


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
        "security_group_id": section.get("security_group_id"),
        "direction": section.get("direction"),
        "action": section.get("action"),
        "protocol": section.get("protocol"),
        "ethertype": section.get("ethertype"),
        "enabled": section.get("enabled"),
        "priority": section.get("priority"),
        "remote_ip_prefix": section.get("remote_ip_prefix"),
        "remote_group_id": section.get("remote_group_id"),
        "remote_address_group_id": section.get("remote_address_group_id"),
        "description": section.get("description"),
        "security_group_rule_id": section.get("security_group_rule_id"),
    }


def list_security_group_rules(
    client,
    *,
    project_id: str,
    query_params: dict[str, Any],
) -> list[dict[str, Any]]:
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v3/{project_id}/security-group-rules",
        query_params=query_params,
    )
    rules = response_data.get("security_group_rules", [])
    if not isinstance(rules, list):
        raise ValueError(
            "Unexpected rule list response: 'security_group_rules' is not a list."
        )
    return rules


def show_security_group_rule(
    client,
    *,
    project_id: str,
    security_group_rule_id: str,
) -> dict[str, Any]:
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v3/{project_id}/security-group-rules/{security_group_rule_id}",
    )
    return response_data.get("security_group_rule", response_data)


def summarize_rule(rule: dict[str, Any]) -> str:
    if not isinstance(rule, dict):
        return "-"
    rule_id = cleaned_str(rule.get("id")) or "-"
    direction = cleaned_str(rule.get("direction")) or "-"
    protocol = cleaned_str(rule.get("protocol")) or "any"
    multiport = cleaned_str(rule.get("multiport")) or "-"
    ether = cleaned_str(rule.get("ethertype")) or "-"
    action = cleaned_str(rule.get("action")) or "-"
    peer = (
        cleaned_str(rule.get("remote_ip_prefix"))
        or cleaned_str(rule.get("remote_group_id"))
        or cleaned_str(rule.get("remote_address_group_id"))
        or "-"
    )
    return (
        f"id={rule_id} | {direction}/{ether}/{protocol}:{multiport} "
        f"| {action} | peer={peer}"
    )


def print_rules(rules: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(rules, indent=2, ensure_ascii=False))
        return

    if not rules:
        print("No security group rules found.")
        return

    for index, rule in enumerate(rules, start=1):
        print(f"{index}. {summarize_rule(rule)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Huawei Cloud VPC security group rules with a standalone script.",
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
        help=f"Maximum number of rules to query. Default is {DEFAULT_LIST_LIMIT}.",
    )
    parser.add_argument("--marker", help="Pagination marker (security group rule ID).")
    parser.add_argument("--id", help="Filter by exact security group rule ID.")
    parser.add_argument(
        "--security-group-id",
        dest="security_group_id",
        help="Filter by parent security group ID.",
    )
    parser.add_argument(
        "--direction",
        choices=tuple(sorted(VALID_DIRECTIONS)),
        help="Filter by direction.",
    )
    parser.add_argument(
        "--action",
        dest="action_filter",
        choices=tuple(sorted(VALID_ACTIONS)),
        help="Filter by action.",
    )
    parser.add_argument("--protocol", help="Filter by protocol, for example tcp/udp/icmp.")
    parser.add_argument(
        "--ethertype",
        choices=tuple(sorted(VALID_ETHERTYPES)),
        help="Filter by ethertype.",
    )
    parser.add_argument(
        "--enabled",
        help="Filter by enabled state (true/false).",
    )
    parser.add_argument("--priority", type=int, help="Filter by priority.")
    parser.add_argument(
        "--remote-ip-prefix",
        dest="remote_ip_prefix",
        help="Filter by remote IP prefix / CIDR.",
    )
    parser.add_argument(
        "--remote-group-id",
        dest="remote_group_id",
        help="Filter by remote security group ID.",
    )
    parser.add_argument(
        "--remote-address-group-id",
        dest="remote_address_group_id",
        help="Filter by remote address group ID.",
    )
    parser.add_argument("--description", help="Filter by description substring.")
    parser.add_argument(
        "--security-group-rule-id",
        dest="security_group_rule_id",
        help="Target rule ID for the 'show' action.",
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

    if args.action == "show":
        rule_id = (
            args.security_group_rule_id
            or cleaned_str(action_defaults.get("security_group_rule_id"))
        )
        if not rule_id:
            raise ValueError(
                "Show requires a security group rule ID. Pass --security-group-rule-id "
                f"or set {SCOPE_SECTION}.security_group_rule_id."
            )
        resource_path = f"/v3/{project_id}/security-group-rules/{rule_id}"
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
        rule = show_security_group_rule(
            client, project_id=project_id, security_group_rule_id=rule_id
        )
        print("Security Group Rule:")
        print(json.dumps(rule, indent=2, ensure_ascii=False))
        return 0

    query_params: dict[str, Any] = {"limit": args.limit}
    marker = args.marker or cleaned_str(action_defaults.get("marker"))
    if marker:
        query_params["marker"] = marker
    id_filter = args.id or cleaned_str(action_defaults.get("id"))
    if id_filter:
        query_params["id"] = id_filter
    security_group_id = args.security_group_id or cleaned_str(
        action_defaults.get("security_group_id")
    )
    if security_group_id:
        query_params["security_group_id"] = security_group_id
    direction = args.direction or cleaned_str(action_defaults.get("direction"))
    if direction:
        query_params["direction"] = direction
    action = args.action_filter or cleaned_str(action_defaults.get("action"))
    if action:
        query_params["action"] = action
    protocol = args.protocol or cleaned_str(action_defaults.get("protocol"))
    if protocol:
        query_params["protocol"] = protocol
    ethertype = args.ethertype or cleaned_str(action_defaults.get("ethertype"))
    if ethertype:
        query_params["ethertype"] = ethertype
    description = args.description or cleaned_str(action_defaults.get("description"))
    if description:
        query_params["description"] = description
    remote_ip_prefix = args.remote_ip_prefix or cleaned_str(
        action_defaults.get("remote_ip_prefix")
    )
    if remote_ip_prefix:
        query_params["remote_ip_prefix"] = remote_ip_prefix
    remote_group_id = args.remote_group_id or cleaned_str(
        action_defaults.get("remote_group_id")
    )
    if remote_group_id:
        query_params["remote_group_id"] = remote_group_id
    remote_address_group_id = args.remote_address_group_id or cleaned_str(
        action_defaults.get("remote_address_group_id")
    )
    if remote_address_group_id:
        query_params["remote_address_group_id"] = remote_address_group_id

    enabled: bool | None
    if args.enabled is not None:
        enabled = normalize_scope_bool(args.enabled)
    else:
        enabled = action_defaults.get("enabled")
    if enabled is not None:
        query_params["enabled"] = enabled
    priority = args.priority or cleaned_str(action_defaults.get("priority"))
    if priority is not None:
        query_params["priority"] = priority

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    if args.dry_run:
        print("Dry run query params:")
        print(json.dumps(query_params, indent=2, ensure_ascii=False))
        return 0

    client = create_api_client(ak, sk, region)
    rules = list_security_group_rules(
        client, project_id=project_id, query_params=query_params
    )
    print(f"Security Group Rule Count: {len(rules)}")
    print_rules(rules, as_json=args.json_output)
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
