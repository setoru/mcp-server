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
    DEFAULT_SCOPE_PATH,
    DEFAULT_SG_ACTION,
    DEFAULT_SG_DIRECTION,
    DEFAULT_SG_ENABLED,
    DEFAULT_SG_ETHERTYPE,
    DEFAULT_SG_PRIORITY,
    DEFAULT_SG_PROTOCOL,
    VPC_ENDPOINT_TEMPLATE,
    VPC_INGRESS_RULE_CREATE_SECTION,
)


SCOPE_SECTION = VPC_INGRESS_RULE_CREATE_SECTION
VALID_ETHERTYPES = {"IPv4", "IPv6"}
VALID_ACTIONS = {"allow", "deny"}
PORTED_PROTOCOLS = {"tcp", "udp"}


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


def normalize_scope_bool(value: Any, *, field: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    cleaned = str(value).strip().lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value for {field}: {value}")


def normalize_int(value: Any, *, field: str) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc


def resolve_action_defaults(scope_config: dict[str, Any]) -> dict[str, Any]:
    section = scope_config.get(SCOPE_SECTION) or {}
    if not isinstance(section, dict):
        raise ValueError(f"Scope section '{SCOPE_SECTION}' must be an object.")
    return {
        "region": section.get("region") or scope_config.get("region"),
        "project_id": section.get("project_id") or scope_config.get("project_id"),
        "security_group_id": section.get("security_group_id"),
        "ethertype": section.get("ethertype"),
        "protocol": section.get("protocol"),
        "multiport": section.get("multiport"),
        "action": section.get("action"),
        "priority": section.get("priority"),
        "enabled": section.get("enabled"),
        "description": section.get("description"),
        "remote_ip_prefix": section.get("remote_ip_prefix"),
        "remote_group_id": section.get("remote_group_id"),
        "remote_address_group_id": section.get("remote_address_group_id"),
    }


def list_security_groups(
    client,
    *,
    project_id: str,
    security_group_id: str,
) -> list[dict[str, Any]]:
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v3/{project_id}/security-groups",
        query_params={"id": security_group_id},
    )
    groups = response_data.get("security_groups", [])
    if not isinstance(groups, list):
        raise ValueError(
            "Unexpected security-group list response: 'security_groups' is not a list."
        )
    return groups


def build_rule_payload(args: argparse.Namespace, defaults: dict[str, Any]) -> dict[str, Any]:
    security_group_id = (
        args.security_group_id or cleaned_str(defaults.get("security_group_id"))
    )
    if not security_group_id:
        raise ValueError(
            "Missing security_group_id. Pass --security-group-id or set "
            f"{SCOPE_SECTION}.security_group_id."
        )

    ethertype = args.ethertype or cleaned_str(defaults.get("ethertype")) or DEFAULT_SG_ETHERTYPE
    if ethertype not in VALID_ETHERTYPES:
        raise ValueError(
            f"Unsupported ethertype: {ethertype}. Supported: {', '.join(sorted(VALID_ETHERTYPES))}."
        )

    protocol = args.protocol or cleaned_str(defaults.get("protocol")) or DEFAULT_SG_PROTOCOL
    protocol_lower = protocol.lower()
    if protocol_lower not in {"tcp", "udp", "icmp", "icmpv6", "any"}:
        raise ValueError(
            f"Unsupported protocol: {protocol}. Supported: tcp, udp, icmp, icmpv6, any."
        )

    action = args.action_filter or cleaned_str(defaults.get("action")) or DEFAULT_SG_ACTION
    if action not in VALID_ACTIONS:
        raise ValueError(
            f"Unsupported action: {action}. Supported: {', '.join(sorted(VALID_ACTIONS))}."
        )

    multiport = args.multiport or cleaned_str(defaults.get("multiport"))
    if protocol_lower in PORTED_PROTOCOLS and not multiport:
        raise ValueError(
            f"Protocol {protocol} requires --multiport (for example 8080 or 8000-9000)."
        )

    remote_ip_prefix = args.remote_ip_prefix or cleaned_str(defaults.get("remote_ip_prefix"))
    remote_group_id = args.remote_group_id or cleaned_str(defaults.get("remote_group_id"))
    remote_address_group_id = args.remote_address_group_id or cleaned_str(
        defaults.get("remote_address_group_id")
    )
    peer_selectors = [
        value
        for value in (remote_ip_prefix, remote_group_id, remote_address_group_id)
        if value
    ]
    if len(peer_selectors) != 1:
        raise ValueError(
            "Exactly one of --remote-ip-prefix, --remote-group-id, or "
            "--remote-address-group-id is required."
        )

    priority = normalize_int(
        args.priority if args.priority is not None else defaults.get("priority"),
        field="priority",
    )
    if priority is not None and not (0 <= priority <= 100):
        raise ValueError("priority must be in the range 0..100.")

    if args.enabled is not None:
        enabled = normalize_scope_bool(args.enabled, field="enabled")
    else:
        enabled_raw = cleaned_str(defaults.get("enabled"))
        enabled = normalize_scope_bool(
            enabled_raw if enabled_raw is not None else DEFAULT_SG_ENABLED,
            field="enabled",
        )

    rule: dict[str, Any] = {
        "security_group_id": security_group_id,
        "direction": DEFAULT_SG_DIRECTION,
        "ethertype": ethertype,
        "protocol": protocol_lower,
        "action": action,
        "enabled": enabled,
    }
    if multiport:
        rule["multiport"] = multiport
    if priority is not None:
        rule["priority"] = priority
    description = args.description or cleaned_str(defaults.get("description"))
    if description:
        rule["description"] = description
    if remote_ip_prefix:
        rule["remote_ip_prefix"] = remote_ip_prefix
    if remote_group_id:
        rule["remote_group_id"] = remote_group_id
    if remote_address_group_id:
        rule["remote_address_group_id"] = remote_address_group_id
    return rule


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


def create_security_group_rule(
    client,
    *,
    project_id: str,
    rule: dict[str, Any],
) -> dict[str, Any]:
    return request_json(
        client,
        method="POST",
        resource_path=f"/v3/{project_id}/security-group-rules",
        body={"security_group_rule": rule},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add one Huawei Cloud VPC security group ingress rule.",
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
        help="Override the project_id from the scope file.",
    )
    parser.add_argument(
        "--security-group-id",
        dest="security_group_id",
        help="Target security group ID.",
    )
    parser.add_argument(
        "--ethertype",
        choices=tuple(sorted(VALID_ETHERTYPES)),
        help=f"Ethernet type. Default: {DEFAULT_SG_ETHERTYPE}.",
    )
    parser.add_argument(
        "--protocol",
        help=f"Protocol (tcp/udp/icmp/icmpv6/any). Default: {DEFAULT_SG_PROTOCOL}.",
    )
    parser.add_argument(
        "--multiport",
        help="Port scope, for example 8080 or 8000-9000. Required for tcp/udp.",
    )
    parser.add_argument(
        "--action",
        dest="action_filter",
        choices=tuple(sorted(VALID_ACTIONS)),
        help=f"Rule action. Default: {DEFAULT_SG_ACTION}.",
    )
    parser.add_argument(
        "--priority",
        type=int,
        help="Rule priority (0..100). Lower numbers match first.",
    )
    parser.add_argument(
        "--enabled",
        help="Rule enabled state (true/false). Default: true.",
    )
    parser.add_argument("--description", help="Rule description.")
    parser.add_argument(
        "--remote-ip-prefix",
        dest="remote_ip_prefix",
        help="Source CIDR or IP for the ingress rule.",
    )
    parser.add_argument(
        "--remote-group-id",
        dest="remote_group_id",
        help="Remote security group ID peer selector.",
    )
    parser.add_argument(
        "--remote-address-group-id",
        dest="remote_address_group_id",
        help="Remote address group ID peer selector.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the target security-group existence preflight check.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved rule payload and exit without sending it.",
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

    defaults = resolve_action_defaults(scope_config)
    region = args.region or cleaned_str(defaults.get("region"))
    project_id = args.project_id or cleaned_str(defaults.get("project_id"))
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")
    if not project_id:
        raise ValueError("Missing project_id. Set it in the scope file or pass --project-id.")

    rule = build_rule_payload(args, defaults)
    resource_path = f"/v3/{project_id}/security-group-rules"

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print(f"Target Security Group: {rule['security_group_id']}")
    print(f"Direction: {rule['direction']}")
    print("Rule payload:")
    print(json.dumps({"security_group_rule": rule}, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("Dry run: no request sent.")
        return 0

    client = create_api_client(ak, sk, region)

    if not args.skip_preflight:
        groups = list_security_groups(
            client, project_id=project_id, security_group_id=rule["security_group_id"]
        )
        if not groups:
            raise ValueError(
                f"Security group {rule['security_group_id']} was not found in this "
                "region/project scope. Re-check the ID or use --skip-preflight to bypass."
            )

    response_data = create_security_group_rule(client, project_id=project_id, rule=rule)
    created_rule = response_data.get("security_group_rule", response_data)
    rule_id = cleaned_str(created_rule.get("id")) if isinstance(created_rule, dict) else None
    if rule_id:
        print(f"Created Rule ID: {rule_id}")
        try:
            read_back = show_security_group_rule(
                client, project_id=project_id, security_group_rule_id=rule_id
            )
            print("Read-back confirmation:")
            print(json.dumps(read_back, indent=2, ensure_ascii=False))
        except Exception as exc:
            print(f"Read-back confirmation failed: {type(exc).__name__} - {exc}", file=sys.stderr)
    else:
        print("Response:")
        print(json.dumps(response_data, indent=2, ensure_ascii=False))
        print("Note: no rule ID returned; request-stage acceptance only.", file=sys.stderr)
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
