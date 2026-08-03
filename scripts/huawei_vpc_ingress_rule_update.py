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
    DEFAULT_SG_DIRECTION,
    VPC_ENDPOINT_TEMPLATE,
    VPC_INGRESS_RULE_UPDATE_SECTION,
)


SCOPE_SECTION = VPC_INGRESS_RULE_UPDATE_SECTION
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
        "security_group_rule_id": section.get("security_group_rule_id"),
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


def update_security_group_rule(
    client,
    *,
    project_id: str,
    security_group_rule_id: str,
    rule: dict[str, Any],
) -> dict[str, Any]:
    return request_json(
        client,
        method="PUT",
        resource_path=f"/v3/{project_id}/security-group-rules/{security_group_rule_id}",
        body={"security_group_rule": rule},
    )


def build_update_payload(
    args: argparse.Namespace,
    defaults: dict[str, Any],
    existing: dict[str, Any],
) -> dict[str, Any]:
    """Merge CLI flags + scope defaults over the existing rule to form the PUT body.

    Huawei's PUT replaces the whole rule, so we start from `existing` and only
    overlay fields the caller actually wanted to change. Direction is pinned to
    ingress and never editable here.
    """
    if not isinstance(existing, dict):
        raise ValueError("Existing rule response is not an object.")

    payload: dict[str, Any] = {
        key: value
        for key, value in existing.items()
        if key not in {"id", "created_at", "updated_at", "tenant_id", "project_id"}
    }
    payload["direction"] = DEFAULT_SG_DIRECTION

    ethertype = args.ethertype or cleaned_str(defaults.get("ethertype"))
    if ethertype:
        if ethertype not in VALID_ETHERTYPES:
            raise ValueError(
                f"Unsupported ethertype: {ethertype}. "
                f"Supported: {', '.join(sorted(VALID_ETHERTYPES))}."
            )
        payload["ethertype"] = ethertype

    protocol = args.protocol or cleaned_str(defaults.get("protocol"))
    if protocol:
        protocol_lower = protocol.lower()
        if protocol_lower not in {"tcp", "udp", "icmp", "icmpv6", "any"}:
            raise ValueError(
                f"Unsupported protocol: {protocol}. Supported: tcp, udp, icmp, icmpv6, any."
            )
        payload["protocol"] = protocol_lower

    action = args.action_filter or cleaned_str(defaults.get("action"))
    if action:
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"Unsupported action: {action}. "
                f"Supported: {', '.join(sorted(VALID_ACTIONS))}."
            )
        payload["action"] = action

    multiport = args.multiport or cleaned_str(defaults.get("multiport"))
    effective_protocol = str(payload.get("protocol", "")).lower()
    if effective_protocol in PORTED_PROTOCOLS and not (multiport or payload.get("multiport")):
        raise ValueError(
            f"Protocol {effective_protocol} requires --multiport "
            "(for example 8080 or 8000-9000)."
        )
    if multiport is not None:
        payload["multiport"] = multiport

    priority = normalize_int(
        args.priority if args.priority is not None else defaults.get("priority"),
        field="priority",
    )
    if priority is not None:
        if not (0 <= priority <= 100):
            raise ValueError("priority must be in the range 0..100.")
        payload["priority"] = priority

    if args.enabled is not None:
        payload["enabled"] = normalize_scope_bool(args.enabled, field="enabled")
    elif defaults.get("enabled") is not None:
        payload["enabled"] = normalize_scope_bool(defaults.get("enabled"), field="enabled")

    description = args.description if args.description is not None else defaults.get("description")
    if description is not None:
        payload["description"] = cleaned_str(description) or ""

    remote_ip_prefix = (
        args.remote_ip_prefix if args.remote_ip_prefix is not None
        else cleaned_str(defaults.get("remote_ip_prefix"))
    )
    remote_group_id = (
        args.remote_group_id if args.remote_group_id is not None
        else cleaned_str(defaults.get("remote_group_id"))
    )
    remote_address_group_id = (
        args.remote_address_group_id if args.remote_address_group_id is not None
        else cleaned_str(defaults.get("remote_address_group_id"))
    )

    provided = [
        value for value in (remote_ip_prefix, remote_group_id, remote_address_group_id)
        if value is not None
    ]
    if len(provided) > 1:
        raise ValueError(
            "Use at most one of --remote-ip-prefix, --remote-group-id, "
            "--remote-address-group-id."
        )

    payload.pop("remote_ip_prefix", None)
    payload.pop("remote_group_id", None)
    payload.pop("remote_address_group_id", None)
    if remote_ip_prefix is not None:
        payload["remote_ip_prefix"] = remote_ip_prefix
    elif remote_group_id is not None:
        payload["remote_group_id"] = remote_group_id
    elif remote_address_group_id is not None:
        payload["remote_address_group_id"] = remote_address_group_id
    else:
        # No peer override supplied: carry over the existing peer selector.
        if cleaned_str(existing.get("remote_ip_prefix")):
            payload["remote_ip_prefix"] = existing["remote_ip_prefix"]
        elif cleaned_str(existing.get("remote_group_id")):
            payload["remote_group_id"] = existing["remote_group_id"]
        elif cleaned_str(existing.get("remote_address_group_id")):
            payload["remote_address_group_id"] = existing["remote_address_group_id"]
        else:
            raise ValueError(
                "An ingress rule requires exactly one of --remote-ip-prefix, "
                "--remote-group-id, or --remote-address-group-id."
            )

    security_group_id = (
        args.security_group_id or cleaned_str(defaults.get("security_group_id"))
        or cleaned_str(existing.get("security_group_id"))
    )
    if not security_group_id:
        raise ValueError("Missing security_group_id on the existing and override rule.")
    payload["security_group_id"] = security_group_id

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Modify one Huawei Cloud VPC security group ingress rule.",
    )
    parser.add_argument("action", choices=("update",))
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
        "--security-group-rule-id",
        dest="security_group_rule_id",
        required=True,
        help="Target ingress rule ID to modify.",
    )
    parser.add_argument(
        "--security-group-id",
        dest="security_group_id",
        help="Override the parent security group ID carried in the PUT body.",
    )
    parser.add_argument(
        "--ethertype",
        choices=tuple(sorted(VALID_ETHERTYPES)),
        help="Update the ethernet type.",
    )
    parser.add_argument(
        "--protocol",
        help="Update the protocol (tcp/udp/icmp/icmpv6/any).",
    )
    parser.add_argument(
        "--multiport",
        help="Update the port scope, for example 8080 or 8000-9000.",
    )
    parser.add_argument(
        "--action",
        dest="action_filter",
        choices=tuple(sorted(VALID_ACTIONS)),
        help="Update the rule action.",
    )
    parser.add_argument(
        "--priority",
        type=int,
        help="Update the rule priority (0..100).",
    )
    parser.add_argument(
        "--enabled",
        help="Update the rule enabled state (true/false).",
    )
    parser.add_argument("--description", help="Update the rule description.")
    parser.add_argument(
        "--remote-ip-prefix",
        dest="remote_ip_prefix",
        help="Update the source CIDR / IP peer selector.",
    )
    parser.add_argument(
        "--remote-group-id",
        dest="remote_group_id",
        help="Update the remote security group ID peer selector.",
    )
    parser.add_argument(
        "--remote-address-group-id",
        dest="remote_address_group_id",
        help="Update the remote address group ID peer selector.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved PUT body and exit without sending it.",
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

    rule_id = args.security_group_rule_id
    resource_path = f"/v3/{project_id}/security-group-rules/{rule_id}"

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print(f"Target Rule ID: {rule_id}")

    client = create_api_client(ak, sk, region)
    existing = show_security_group_rule(
        client, project_id=project_id, security_group_rule_id=rule_id
    )
    existing_direction = cleaned_str(existing.get("direction")) if isinstance(existing, dict) else None
    if existing_direction and existing_direction != DEFAULT_SG_DIRECTION:
        raise ValueError(
            f"Rule {rule_id} is direction={existing_direction}, not ingress. "
            "This script only modifies ingress rules."
        )

    payload = build_update_payload(args, defaults, existing)
    print("Resolved PUT body:")
    print(json.dumps({"security_group_rule": payload}, indent=2, ensure_ascii=False))

    if args.dry_run:
        print("Dry run: no request sent.")
        return 0

    response_data = update_security_group_rule(
        client, project_id=project_id, security_group_rule_id=rule_id, rule=payload
    )
    print("Updated rule:")
    print(json.dumps(response_data, indent=2, ensure_ascii=False))
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
