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


VPC_ENDPOINT_TEMPLATE = "vpc.{region}.myhuaweicloud.com"
DEFAULT_LIST_LIMIT = 2000
IDLE_STATUSES = {"DOWN", "FREEZED", "ERROR"}
VALID_STATUSES = {"FREEZED", "DOWN", "ACTIVE", "ERROR"}


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


def is_idle_publicip(publicip: dict[str, Any]) -> bool:
    status = cleaned_str(publicip.get("status")) or ""
    associate_instance_type = cleaned_str(publicip.get("associate_instance_type"))
    associate_instance_id = cleaned_str(publicip.get("associate_instance_id"))
    vnic = publicip.get("vnic")
    return (
        status in IDLE_STATUSES
        and not associate_instance_type
        and not associate_instance_id
        and not vnic
    )


def format_association(publicip: dict[str, Any]) -> str:
    associate_instance_type = cleaned_str(publicip.get("associate_instance_type"))
    associate_instance_id = cleaned_str(publicip.get("associate_instance_id"))
    vnic = publicip.get("vnic") if isinstance(publicip.get("vnic"), dict) else {}
    vnic_instance_type = cleaned_str(vnic.get("instance_type"))
    vnic_instance_id = cleaned_str(vnic.get("instance_id"))
    vnic_port_id = cleaned_str(vnic.get("port_id"))

    parts: list[str] = []
    if associate_instance_type or associate_instance_id:
        parts.append(
            f"{associate_instance_type or '-'}:{associate_instance_id or '-'}"
        )
    if vnic_instance_type or vnic_instance_id:
        parts.append(f"{vnic_instance_type or '-'}:{vnic_instance_id or '-'}")
    if vnic_port_id:
        parts.append(f"port:{vnic_port_id}")
    return ", ".join(parts) if parts else "-"


def format_bandwidth(publicip: dict[str, Any]) -> str:
    bandwidth = publicip.get("bandwidth")
    if not isinstance(bandwidth, dict):
        return "-"
    size = cleaned_str(bandwidth.get("size")) or "-"
    charge_mode = cleaned_str(bandwidth.get("charge_mode")) or "-"
    share_type = cleaned_str(bandwidth.get("share_type")) or "-"
    return f"{size}Mbps/{charge_mode}/{share_type}"


def fetch_publicips(
    client,
    *,
    project_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v3/{project_id}/eip/publicips",
        query_params={"limit": limit},
    )
    publicips = response_data.get("publicips", [])
    if not isinstance(publicips, list):
        raise ValueError("Unexpected EIP list response: 'publicips' is not a list.")
    return publicips


def filter_publicips(
    publicips: list[dict[str, Any]],
    *,
    publicip_ids: list[str],
    public_ip_addresses: list[str],
    statuses: list[str],
    publicip_pool_name: str | None,
    idle_only: bool,
) -> list[dict[str, Any]]:
    id_set = set(publicip_ids)
    address_set = set(public_ip_addresses)
    status_set = set(statuses)

    filtered: list[dict[str, Any]] = []
    for publicip in publicips:
        publicip_id = cleaned_str(publicip.get("id")) or ""
        public_ip_address = cleaned_str(publicip.get("public_ip_address")) or ""
        status = cleaned_str(publicip.get("status")) or ""
        pool_name = cleaned_str(publicip.get("publicip_pool_name"))

        if id_set and publicip_id not in id_set:
            continue
        if address_set and public_ip_address not in address_set:
            continue
        if status_set and status not in status_set:
            continue
        if publicip_pool_name and pool_name != publicip_pool_name:
            continue
        if idle_only and not is_idle_publicip(publicip):
            continue
        filtered.append(publicip)
    return filtered


def print_publicips(publicips: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(publicips, indent=2, ensure_ascii=False))
        return

    if not publicips:
        print("No EIPs found.")
        return

    for index, publicip in enumerate(publicips, start=1):
        public_ip_address = cleaned_str(publicip.get("public_ip_address")) or "-"
        publicip_id = cleaned_str(publicip.get("id")) or "-"
        status = cleaned_str(publicip.get("status")) or "-"
        idle = "true" if is_idle_publicip(publicip) else "false"
        print(
            f"{index}. {public_ip_address} | "
            f"id={publicip_id} | "
            f"status={status} | "
            f"idle={idle} | "
            f"bound={format_association(publicip)} | "
            f"bandwidth={format_bandwidth(publicip)}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query or delete Huawei Cloud EIPs with a standalone script.",
    )
    parser.add_argument("action", choices=("list", "delete"))
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
        "--dry-run",
        action="store_true",
        help="Resolve targets and print results without sending delete requests.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help="Maximum number of EIP records to query. Default is 2000.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full EIP results as JSON.",
    )
    parser.add_argument(
        "--publicip-id",
        dest="publicip_ids",
        action="append",
        help="Target EIP ID. Repeat or use comma-separated values.",
    )
    parser.add_argument(
        "--public-ip-address",
        dest="public_ip_addresses",
        action="append",
        help="Target public IP address. Repeat or use comma-separated values.",
    )
    parser.add_argument(
        "--status",
        dest="statuses",
        action="append",
        help="Filter by status. Repeat or use comma-separated values.",
    )
    parser.add_argument(
        "--publicip-pool-name",
        help="Filter by publicip_pool_name, for example 5_bgp.",
    )
    parser.add_argument(
        "--idle-only",
        action="store_true",
        help="Only match idle EIPs: unassociated and in DOWN/FREEZED/ERROR status.",
    )
    parser.add_argument(
        "--all-matches",
        action="store_true",
        help="Allow deleting multiple matched EIPs in one run.",
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

    region = args.region or cleaned_str(scope_config.get("region"))
    project_id = args.project_id or cleaned_str(scope_config.get("project_id"))
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")
    if not project_id:
        raise ValueError("Missing project_id. Set it in the scope file or pass --project-id.")
    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    publicip_ids = split_csv_values(args.publicip_ids)
    public_ip_addresses = split_csv_values(args.public_ip_addresses)
    statuses = split_csv_values(args.statuses)
    invalid_statuses = [status for status in statuses if status not in VALID_STATUSES]
    if invalid_statuses:
        raise ValueError(
            f"Unsupported status values: {', '.join(invalid_statuses)}. "
            f"Supported values: {', '.join(sorted(VALID_STATUSES))}."
        )

    client = create_api_client(ak, sk, region)
    publicips = fetch_publicips(client, project_id=project_id, limit=args.limit)
    matched_publicips = filter_publicips(
        publicips,
        publicip_ids=publicip_ids,
        public_ip_addresses=public_ip_addresses,
        statuses=statuses,
        publicip_pool_name=args.publicip_pool_name,
        idle_only=args.idle_only,
    )

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print(f"Matched EIP Count: {len(matched_publicips)}")

    if args.action == "list":
        print_publicips(matched_publicips, as_json=args.json_output)
        return 0

    if not any(
        (
            publicip_ids,
            public_ip_addresses,
            statuses,
            args.publicip_pool_name,
            args.idle_only,
        )
    ):
        raise ValueError(
            "Delete requires at least one selector such as --publicip-id, "
            "--public-ip-address, --status, --publicip-pool-name, or --idle-only."
        )

    if not matched_publicips:
        print("No EIPs matched the delete filters.")
        return 0

    associated_targets = [
        publicip
        for publicip in matched_publicips
        if not is_idle_publicip(publicip)
    ]
    if associated_targets:
        raise ValueError(
            "Refusing to delete associated or non-idle EIPs. "
            "Use filters that only match unassociated idle EIPs."
        )

    if len(matched_publicips) > 1 and not args.all_matches:
        raise ValueError(
            f"Matched {len(matched_publicips)} EIPs. Re-run with --all-matches to delete them."
        )

    if args.dry_run:
        print("Dry run targets:")
        print_publicips(matched_publicips, as_json=args.json_output)
        return 0

    deleted_targets: list[dict[str, str]] = []
    for index, publicip in enumerate(matched_publicips, start=1):
        publicip_id = cleaned_str(publicip.get("id")) or ""
        public_ip_address = cleaned_str(publicip.get("public_ip_address")) or "-"
        print(f"Deleting EIP {index}/{len(matched_publicips)}: {public_ip_address} ({publicip_id})")
        request_json(
            client,
            method="DELETE",
            resource_path=f"/v3/{project_id}/eip/publicips/{publicip_id}",
            body=None,
        )
        deleted_targets.append(
            {"id": publicip_id, "public_ip_address": public_ip_address}
        )

    print("Deleted EIPs:")
    print(json.dumps(deleted_targets, indent=2, ensure_ascii=False))
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
