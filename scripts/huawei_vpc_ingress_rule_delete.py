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
    VPC_ENDPOINT_TEMPLATE,
    VPC_INGRESS_RULE_DELETE_SECTION,
)


SCOPE_SECTION = VPC_INGRESS_RULE_DELETE_SECTION


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


def resolve_action_defaults(scope_config: dict[str, Any]) -> dict[str, Any]:
    section = scope_config.get(SCOPE_SECTION) or {}
    if not isinstance(section, dict):
        raise ValueError(f"Scope section '{SCOPE_SECTION}' must be an object.")
    return {
        "region": section.get("region") or scope_config.get("region"),
        "project_id": section.get("project_id") or scope_config.get("project_id"),
        "security_group_rule_id": section.get("security_group_rule_id"),
        "security_group_id": section.get("security_group_id"),
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
        resource_path=f"/v3/{project_id}/vpc/security-group-rules/{security_group_rule_id}",
    )
    return response_data.get("security_group_rule", response_data)


def delete_security_group_rule(
    client,
    *,
    project_id: str,
    security_group_rule_id: str,
) -> dict[str, Any]:
    return request_json(
        client,
        method="DELETE",
        resource_path=f"/v3/{project_id}/vpc/security-group-rules/{security_group_rule_id}",
    )


def summarize_rule(rule: dict[str, Any]) -> str:
    if not isinstance(rule, dict):
        return "-"
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
    return f"{direction}/{ether}/{protocol}:{multiport} {action} <- {peer}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete one Huawei Cloud VPC security group ingress rule by exact rule ID.",
    )
    parser.add_argument("action", choices=("delete",))
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
        help="Target ingress rule ID to delete.",
    )
    parser.add_argument(
        "--security-group-id",
        dest="security_group_id",
        help="Optional extra guard: only delete if the rule belongs to this security group.",
    )
    parser.add_argument(
        "--allow-egress",
        action="store_true",
        help="Allow deleting egress rules too. Default: only ingress rules.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the preflight existence/direction check before deletion.",
    )
    parser.add_argument(
        "--skip-recheck",
        action="store_true",
        help="Skip the final visibility recheck after deletion.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved target and preflight result, then exit without deleting.",
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

    rule_id = args.security_group_rule_id or cleaned_str(
        defaults.get("security_group_rule_id")
    )
    if not rule_id:
        raise ValueError(
            "Missing security_group_rule_id. Pass --security-group-rule-id or set "
            f"{SCOPE_SECTION}.security_group_rule_id."
        )
    guard_security_group_id = args.security_group_id or cleaned_str(
        defaults.get("security_group_id")
    )

    delete_path = f"/v3/{project_id}/vpc/security-group-rules/{rule_id}"

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print(f"Target Rule ID: {rule_id}")
    if guard_security_group_id:
        print(f"Guard Security Group ID: {guard_security_group_id}")

    client = create_api_client(ak, sk, region)

    preflight_rule: dict[str, Any] = {}
    if not args.skip_preflight:
        try:
            preflight_rule = show_security_group_rule(
                client, project_id=project_id, security_group_rule_id=rule_id
            )
        except Exception as exc:
            raise ValueError(
                f"Preflight lookup for rule {rule_id} failed: "
                f"{type(exc).__name__} - {exc}"
            ) from exc

        if not isinstance(preflight_rule, dict) or not preflight_rule:
            raise ValueError(
                f"Target rule {rule_id} was not found in this region/project scope."
            )

        direction = cleaned_str(preflight_rule.get("direction"))
        if direction != "ingress" and not args.allow_egress:
            raise ValueError(
                f"Rule {rule_id} is direction={direction}, not ingress. "
                "This script only deletes ingress rules by default; "
                "pass --allow-egress to delete egress rules too."
            )

        if guard_security_group_id:
            rule_group_id = cleaned_str(preflight_rule.get("security_group_id"))
            if rule_group_id != guard_security_group_id:
                raise ValueError(
                    f"Guard mismatch: rule {rule_id} belongs to security group "
                    f"{rule_group_id or '-'}, not {guard_security_group_id}."
                )
        print(f"Preflight: rule found ({summarize_rule(preflight_rule)})")
    else:
        print("Preflight: skipped")

    if args.dry_run:
        print("Dry run: no delete request sent.")
        return 0

    print(f"Deleting rule {rule_id} ...")
    delete_response = delete_security_group_rule(
        client, project_id=project_id, security_group_rule_id=rule_id
    )
    print("Delete response:")
    print(json.dumps(delete_response, indent=2, ensure_ascii=False))

    if args.skip_recheck:
        print("Final recheck: skipped")
        return 0

    try:
        recheck = show_security_group_rule(
            client, project_id=project_id, security_group_rule_id=rule_id
        )
    except Exception as exc:
        print(
            f"Final recheck: delete likely succeeded (rule no longer queryable). "
            f"Recheck error: {type(exc).__name__} - {exc}",
            file=sys.stderr,
        )
        return 0

    if isinstance(recheck, dict) and recheck:
        raise ValueError(
            f"Rule {rule_id} is still visible after deletion; delete may be blocked "
            "or incomplete."
        )
    print(f"Final recheck: rule {rule_id} is no longer visible in this scope.")
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
