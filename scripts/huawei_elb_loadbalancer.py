from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

import yaml
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.client import Client, ClientBuilder
from huaweicloudsdkcore.exceptions.exceptions import HostUnreachableException
from huaweicloudsdkcore.region.region import Region
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.sdk_response import FutureSdkResponse
from huaweicloudsdkcore.utils import http_utils

from huawei_scope import (
    DEFAULT_CREATE_COUNT,
    DEFAULT_LIST_LIMIT,
    DEFAULT_RANDOM_NAME_PREFIX,
    DEFAULT_SCOPE_PATH,
    ELB_ENDPOINT_TEMPLATE,
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
    endpoint = f"https://{ELB_ENDPOINT_TEMPLATE.replace('{region}', region)}"
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


def load_scope_config(scope_path: Path) -> dict[str, Any]:
    with open(scope_path, "r", encoding="utf-8") as handle:
        scope_config = yaml.safe_load(handle) or {}
    if not isinstance(scope_config, dict):
        raise ValueError("Scope file content must be an object mapping.")
    if isinstance(scope_config.get("default"), dict):
        scope_config = scope_config["default"]
    return scope_config


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


def cleaned_str(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def normalize_scope_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"Unsupported integer value: {value}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unsupported integer value: {value}") from exc


def generate_random_name(prefix: str, *, index: int | None = None) -> str:
    cleaned_prefix = cleaned_str(prefix) or DEFAULT_RANDOM_NAME_PREFIX
    trimmed_prefix = cleaned_prefix[:48]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    random_suffix = uuid4().hex[:8]
    name = f"{trimmed_prefix}-{timestamp}-{random_suffix}"
    if index is not None:
        name = f"{name}-{index:02d}"
    return name[:255]


def generate_bandwidth_name(loadbalancer_name: str) -> str:
    return f"{loadbalancer_name}-bw"[:64]


def normalize_create_loadbalancer(loadbalancer: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(loadbalancer)
    vip_subnet_cidr_id = cleaned_str(normalized.get("vip_subnet_cidr_id"))
    vip_subnet_id = cleaned_str(normalized.get("vip_subnet_id"))
    if not vip_subnet_cidr_id and vip_subnet_id:
        normalized["vip_subnet_cidr_id"] = vip_subnet_id
    normalized.pop("vip_subnet_id", None)
    return normalized


def validate_create_loadbalancer(loadbalancer: dict[str, Any]) -> None:
    vip_subnet_cidr_id = cleaned_str(loadbalancer.get("vip_subnet_cidr_id"))
    if not vip_subnet_cidr_id:
        raise ValueError(
            "Missing vip_subnet_cidr_id. Set elb_create.loadbalancer.vip_subnet_cidr_id "
            "(or legacy vip_subnet_id) in the scope file or pass --vip-subnet-id."
        )

    availability_zone_list = loadbalancer.get("availability_zone_list")
    if not isinstance(availability_zone_list, list) or not availability_zone_list:
        raise ValueError(
            "Missing availability_zone_list. Set elb_create.loadbalancer.availability_zone_list "
            "in the scope file or pass one or more --availability-zone values."
        )
    if any(not cleaned_str(item) for item in availability_zone_list):
        raise ValueError("availability_zone_list must contain non-empty strings.")

    if loadbalancer.get("guaranteed") is True and not cleaned_str(loadbalancer.get("l4_flavor_id")):
        raise ValueError(
            "Dedicated ELB creation requires l4_flavor_id. Set it in the scope file or pass --l4-flavor-id."
        )

    publicip = loadbalancer.get("publicip")
    if publicip is None:
        return
    if not isinstance(publicip, dict):
        raise ValueError("loadbalancer.publicip must be an object.")

    if not cleaned_str(publicip.get("network_type")):
        raise ValueError(
            "publicip.network_type is required when creating a public IP. "
            "Set it in the scope file or pass --publicip-network-type."
        )

    bandwidth = publicip.get("bandwidth")
    if not isinstance(bandwidth, dict):
        raise ValueError(
            "publicip.bandwidth is required when creating a public IP. "
            "Set it in the scope file or pass the public IP bandwidth options."
        )

    if normalize_scope_int(bandwidth.get("size")) is None:
        raise ValueError(
            "publicip.bandwidth.size is required when creating a public IP. "
            "Set it in the scope file or pass --publicip-size."
        )
    if not cleaned_str(bandwidth.get("share_type")):
        raise ValueError(
            "publicip.bandwidth.share_type is required when creating a public IP. "
            "Set it in the scope file or pass --publicip-share-type."
        )
    if not cleaned_str(bandwidth.get("charge_mode")):
        raise ValueError(
            "publicip.bandwidth.charge_mode is required when creating a public IP. "
            "Set it in the scope file or pass --publicip-charge-mode."
        )


def resolve_action_defaults(scope_config: dict[str, Any], action: str) -> dict[str, Any]:
    section_name = f"elb_{action}"
    section = scope_config.get(section_name) or {}
    if not isinstance(section, dict):
        raise ValueError(f"Scope section '{section_name}' must be an object.")

    defaults: dict[str, Any] = {
        "region": section.get("region") or scope_config.get("region"),
        "project_id": section.get("project_id") or scope_config.get("project_id"),
    }

    if action == "list":
        defaults.update(
            {
                "id": section.get("id"),
                "name": section.get("name"),
                "provisioning_status": section.get("provisioning_status"),
                "operating_status": section.get("operating_status"),
                "vip_address": section.get("vip_address"),
                "vip_subnet_id": section.get("vip_subnet_id"),
                "vpc_id": section.get("vpc_id"),
                "admin_state_up": normalize_scope_bool(section.get("admin_state_up")),
                "enterprise_project_id": section.get("enterprise_project_id"),
                "limit": section.get("limit"),
                "marker": section.get("marker"),
            }
        )
    elif action == "create":
        loadbalancer = section.get("loadbalancer") or {}
        if not isinstance(loadbalancer, dict):
            raise ValueError("Scope 'elb_create.loadbalancer' must be an object.")
        defaults["loadbalancer"] = loadbalancer
        defaults["count"] = section.get("count")
        defaults["random_name"] = normalize_scope_bool(section.get("random_name"))
        defaults["name_prefix"] = section.get("name_prefix")
    elif action == "delete":
        defaults["loadbalancer_id"] = section.get("loadbalancer_id")

    return defaults


def list_loadbalancers(
    client,
    *,
    project_id: str,
    query_params: dict[str, Any],
) -> list[dict[str, Any]]:
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v2/{project_id}/elb/loadbalancers",
        query_params=query_params,
    )
    loadbalancers = response_data.get("loadbalancers", [])
    if not isinstance(loadbalancers, list):
        raise ValueError("Unexpected ELB list response: 'loadbalancers' is not a list.")
    return loadbalancers


def safe_get_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    return str(value).strip() if value not in (None, "") else "-"


def print_loadbalancer_list(loadbalancers: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(loadbalancers, indent=2, ensure_ascii=False))
        return

    if not loadbalancers:
        print("No load balancers found.")
        return

    for index, lb in enumerate(loadbalancers, start=1):
        print(
            f"{index}. {safe_get_str(lb, 'name')} | "
            f"id={safe_get_str(lb, 'id')} | "
            f"provisioning={safe_get_str(lb, 'provisioning_status')} | "
            f"operating={safe_get_str(lb, 'operating_status')} | "
            f"vip={safe_get_str(lb, 'vip_address')} | "
            f"vip_subnet_id={safe_get_str(lb, 'vip_subnet_id')} | "
            f"vip_port_id={safe_get_str(lb, 'vip_port_id')}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, list, or delete Huawei Cloud ELB load balancers with a standalone script.",
    )
    parser.add_argument("action", choices=("list", "create", "delete"))
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
        help="Print the resolved request and exit without sending it.",
    )

    # list filters (also used by create when relevant)
    parser.add_argument("--id", dest="id_filter", help="Filter by load balancer id.")
    parser.add_argument("--name", help="Filter by name (exact match) or set name when creating.")
    parser.add_argument(
        "--provisioning-status",
        dest="provisioning_status",
        help="Filter by provisioning_status, e.g. ACTIVE.",
    )
    parser.add_argument(
        "--operating-status",
        dest="operating_status",
        help="Filter by operating_status, e.g. ONLINE.",
    )
    parser.add_argument("--vip-address", dest="vip_address", help="Filter/set VIP address.")
    parser.add_argument(
        "--vip-subnet-id",
        dest="vip_subnet_id",
        help="Filter by vip_subnet_id, or set vip_subnet_cidr_id when creating.",
    )
    parser.add_argument("--vpc-id", dest="vpc_id", help="Filter by vpc_id.")
    parser.add_argument(
        "--admin-state-up",
        dest="admin_state_up",
        choices=("true", "false"),
        help="Filter/set admin_state_up.",
    )
    parser.add_argument(
        "--enterprise-project-id",
        dest="enterprise_project_id",
        help="Filter/set enterprise_project_id.",
    )
    parser.add_argument("--marker", help="Pagination marker.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help="Maximum number of ELB records to query. Default is 1000.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full ELB results as JSON (list action only).",
    )

    # create-only fields
    parser.add_argument("--description", help="Set load balancer description (create only).")
    parser.add_argument(
        "--count",
        type=int,
        default=DEFAULT_CREATE_COUNT,
        help="Number of ELBs to create in one run. Default is 1.",
    )
    parser.add_argument(
        "--random-name",
        action="store_true",
        help="Generate a random ELB name. When --count > 1, unique names are generated automatically.",
    )
    parser.add_argument(
        "--name-prefix",
        help="Prefix used for generated ELB names when --random-name is enabled or --count > 1.",
    )
    parser.add_argument(
        "--availability-zone",
        dest="availability_zones",
        action="append",
        help="Availability zone for create. Repeat this option to specify multiple AZs.",
    )
    parser.add_argument("--l4-flavor-id", dest="l4_flavor_id", help="Set l4_flavor_id.")
    parser.add_argument("--l7-flavor-id", dest="l7_flavor_id", help="Set l7_flavor_id.")
    parser.add_argument(
        "--charge-mode",
        dest="lb_charge_mode",
        choices=("flavor", "lcu"),
        help="Set ELB charge_mode.",
    )
    guaranteed_group = parser.add_mutually_exclusive_group()
    guaranteed_group.add_argument(
        "--guaranteed",
        dest="guaranteed",
        action="store_true",
        help="Create dedicated ELBs.",
    )
    guaranteed_group.add_argument(
        "--shared",
        dest="guaranteed",
        action="store_false",
        help="Create shared ELBs.",
    )
    parser.set_defaults(guaranteed=None)
    parser.add_argument(
        "--with-publicip",
        action="store_true",
        help="Create and bind a public IP while creating the ELB.",
    )
    parser.add_argument(
        "--publicip-network-type",
        dest="publicip_network_type",
        help="Set publicip.network_type, for example 5_bgp.",
    )
    parser.add_argument(
        "--publicip-ip-version",
        dest="publicip_ip_version",
        type=int,
        choices=(4, 6),
        help="Set publicip.ip_version.",
    )
    parser.add_argument(
        "--publicip-description",
        dest="publicip_description",
        help="Set publicip.description.",
    )
    parser.add_argument(
        "--publicip-size",
        dest="publicip_size",
        type=int,
        help="Set publicip.bandwidth.size.",
    )
    parser.add_argument(
        "--publicip-share-type",
        dest="publicip_share_type",
        choices=("PER", "WHOLE"),
        help="Set publicip.bandwidth.share_type.",
    )
    parser.add_argument(
        "--publicip-charge-mode",
        dest="publicip_charge_mode",
        choices=("bandwidth", "traffic"),
        help="Set publicip.bandwidth.charge_mode.",
    )
    parser.add_argument(
        "--publicip-bandwidth-name",
        dest="publicip_bandwidth_name",
        help="Set publicip.bandwidth.name.",
    )
    parser.add_argument(
        "--protection-status",
        dest="protection_status",
        choices=("nonProtection", "consoleProtection"),
        help="Set protection_status (create only).",
    )
    parser.add_argument(
        "--protection-reason",
        dest="protection_reason",
        help="Set protection_reason (create only).",
    )

    # delete-only fields
    parser.add_argument(
        "--loadbalancer-id",
        dest="loadbalancer_id",
        help="Target load balancer id for delete (recommended).",
    )
    delete_mode_group = parser.add_mutually_exclusive_group()
    delete_mode_group.add_argument(
        "--cascade",
        dest="cascade",
        action="store_true",
        help="Use cascade deletion (default, also affects associated resources).",
    )
    delete_mode_group.add_argument(
        "--no-cascade",
        dest="cascade",
        action="store_false",
        help="Use standard delete instead of cascade deletion.",
    )
    parser.set_defaults(cascade=True)
    parser.add_argument(
        "--keep-public-ip",
        action="store_true",
        help="When using cascade deletion, keep the associated public IP instead of deleting it.",
    )
    parser.add_argument(
        "--keep-unbounded-pool",
        action="store_true",
        help="When using cascade deletion, keep the associated unbounded pool instead of deleting it.",
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

    action_defaults = resolve_action_defaults(scope_config, args.action)
    region = args.region or cleaned_str(action_defaults.get("region"))
    project_id = args.project_id or cleaned_str(action_defaults.get("project_id"))
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")
    if not project_id:
        raise ValueError("Missing project_id. Set it in the scope file or pass --project-id.")
    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    client = create_api_client(ak, sk, region, project_id=project_id)

    if args.action == "list":
        limit = args.limit
        scope_limit = action_defaults.get("limit")
        if limit == DEFAULT_LIST_LIMIT and isinstance(scope_limit, int) and scope_limit > 0:
            limit = scope_limit

        query_params: dict[str, Any] = {"limit": limit}
        marker = args.marker or cleaned_str(action_defaults.get("marker"))
        if marker:
            query_params["marker"] = marker

        id_filter = args.id_filter or cleaned_str(action_defaults.get("id"))
        if id_filter:
            query_params["id"] = id_filter

        name = args.name or cleaned_str(action_defaults.get("name"))
        if name:
            query_params["name"] = name

        provisioning_status = args.provisioning_status or cleaned_str(
            action_defaults.get("provisioning_status")
        )
        if provisioning_status:
            query_params["provisioning_status"] = provisioning_status

        operating_status = args.operating_status or cleaned_str(
            action_defaults.get("operating_status")
        )
        if operating_status:
            query_params["operating_status"] = operating_status

        vip_address = args.vip_address or cleaned_str(action_defaults.get("vip_address"))
        if vip_address:
            query_params["vip_address"] = vip_address

        vip_subnet_id = args.vip_subnet_id or cleaned_str(action_defaults.get("vip_subnet_id"))
        if vip_subnet_id:
            query_params["vip_subnet_id"] = vip_subnet_id

        vpc_id = args.vpc_id or cleaned_str(action_defaults.get("vpc_id"))
        if vpc_id:
            query_params["vpc_id"] = vpc_id

        admin_state_up: bool | None
        if args.admin_state_up is not None:
            admin_state_up = normalize_scope_bool(args.admin_state_up)
        else:
            admin_state_up = action_defaults.get("admin_state_up")
        if admin_state_up is not None:
            query_params["admin_state_up"] = admin_state_up

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

        loadbalancers = list_loadbalancers(
            client, project_id=project_id, query_params=query_params
        )
        print(f"ELB Count: {len(loadbalancers)}")
        print_loadbalancer_list(loadbalancers, as_json=args.json_output)
        return 0

    if args.action == "create":
        scope_lb = action_defaults.get("loadbalancer") or {}
        if not isinstance(scope_lb, dict):
            scope_lb = {}

        scope_count = normalize_scope_int(action_defaults.get("count"))
        count = args.count
        if count == DEFAULT_CREATE_COUNT and scope_count is not None:
            count = scope_count
        if count < 1:
            raise ValueError("--count must be greater than or equal to 1.")

        scope_random_name = action_defaults.get("random_name")
        random_name = bool(scope_random_name) or bool(args.random_name)

        loadbalancer: dict[str, Any] = deepcopy(scope_lb)
        if args.vip_subnet_id:
            loadbalancer["vip_subnet_cidr_id"] = args.vip_subnet_id
        if args.name:
            loadbalancer["name"] = args.name
        if args.description:
            loadbalancer["description"] = args.description
        if args.vip_address:
            loadbalancer["vip_address"] = args.vip_address
        if args.availability_zones:
            loadbalancer["availability_zone_list"] = args.availability_zones
        if args.l4_flavor_id:
            loadbalancer["l4_flavor_id"] = args.l4_flavor_id
        if args.l7_flavor_id:
            loadbalancer["l7_flavor_id"] = args.l7_flavor_id
        if args.lb_charge_mode:
            loadbalancer["charge_mode"] = args.lb_charge_mode
        if args.guaranteed is not None:
            loadbalancer["guaranteed"] = args.guaranteed
        if args.admin_state_up is not None:
            loadbalancer["admin_state_up"] = normalize_scope_bool(args.admin_state_up)
        if args.enterprise_project_id:
            loadbalancer["enterprise_project_id"] = args.enterprise_project_id
        if args.protection_status:
            loadbalancer["protection_status"] = args.protection_status
        if args.protection_reason:
            loadbalancer["protection_reason"] = args.protection_reason

        publicip_requested = args.with_publicip or any(
            value is not None
            for value in (
                args.publicip_network_type,
                args.publicip_ip_version,
                args.publicip_description,
                args.publicip_size,
                args.publicip_share_type,
                args.publicip_charge_mode,
                args.publicip_bandwidth_name,
            )
        )
        existing_publicip = loadbalancer.get("publicip")
        if existing_publicip not in (None, {}) and not isinstance(existing_publicip, dict):
            raise ValueError("Scope 'elb_create.loadbalancer.publicip' must be an object.")
        if publicip_requested or isinstance(existing_publicip, dict):
            publicip = deepcopy(existing_publicip or {})
            existing_bandwidth = publicip.get("bandwidth")
            if existing_bandwidth not in (None, {}) and not isinstance(existing_bandwidth, dict):
                raise ValueError("Scope 'elb_create.loadbalancer.publicip.bandwidth' must be an object.")
            bandwidth = deepcopy(existing_bandwidth or {})

            if args.publicip_network_type:
                publicip["network_type"] = args.publicip_network_type
            if args.publicip_ip_version is not None:
                publicip["ip_version"] = args.publicip_ip_version
            if args.publicip_description:
                publicip["description"] = args.publicip_description
            if args.publicip_size is not None:
                bandwidth["size"] = args.publicip_size
            if args.publicip_share_type:
                bandwidth["share_type"] = args.publicip_share_type
            if args.publicip_charge_mode:
                bandwidth["charge_mode"] = args.publicip_charge_mode
            if args.publicip_bandwidth_name:
                bandwidth["name"] = args.publicip_bandwidth_name

            if bandwidth:
                publicip["bandwidth"] = bandwidth
            loadbalancer["publicip"] = publicip

        loadbalancer = normalize_create_loadbalancer(loadbalancer)
        validate_create_loadbalancer(loadbalancer)

        configured_name_prefix = (
            args.name_prefix
            or cleaned_str(action_defaults.get("name_prefix"))
            or cleaned_str(loadbalancer.get("name"))
            or DEFAULT_RANDOM_NAME_PREFIX
        )
        generate_unique_names = random_name or count > 1

        print(f"Action: {args.action}")
        print(f"Scope: {scope_path}")
        print(f"Region: {region}")
        print(f"Project ID: {project_id}")
        print(f"Create Count: {count}")

        request_bodies: list[dict[str, Any]] = []
        for index in range(1, count + 1):
            request_loadbalancer = deepcopy(loadbalancer)
            if generate_unique_names:
                generated_name = generate_random_name(
                    configured_name_prefix,
                    index=index if count > 1 else None,
                )
                request_loadbalancer["name"] = generated_name
                publicip = request_loadbalancer.get("publicip")
                if isinstance(publicip, dict):
                    bandwidth = publicip.get("bandwidth")
                    if isinstance(bandwidth, dict) and not cleaned_str(bandwidth.get("name")):
                        bandwidth["name"] = generate_bandwidth_name(generated_name)
            request_bodies.append({"loadbalancer": request_loadbalancer})

        if args.dry_run:
            print("Dry run request:")
            payload: Any = request_bodies[0] if len(request_bodies) == 1 else request_bodies
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0

        responses: list[dict[str, Any]] = []
        for index, request_body in enumerate(request_bodies, start=1):
            request_name = request_body["loadbalancer"].get("name", "-")
            print(f"Submitting create request {index}/{count}: name={request_name}")
            response_data = request_json(
                client,
                method="POST",
                resource_path=f"/v3/{project_id}/elb/loadbalancers",
                body=request_body,
            )
            responses.append(
                {
                    "index": index,
                    "name": request_name,
                    "response": response_data,
                }
            )

        print("Response:")
        payload = responses[0]["response"] if len(responses) == 1 else responses
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    # delete
    loadbalancer_id = args.loadbalancer_id or cleaned_str(action_defaults.get("loadbalancer_id"))
    if not loadbalancer_id:
        raise ValueError(
            "Missing loadbalancer_id. Pass --loadbalancer-id or set elb_delete.loadbalancer_id in the scope file."
        )

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print(f"Target Load Balancer ID: {loadbalancer_id}")

    if args.keep_public_ip and not args.cascade:
        raise ValueError("--keep-public-ip requires cascade deletion. Remove --no-cascade to use it.")
    if args.keep_unbounded_pool and not args.cascade:
        raise ValueError(
            "--keep-unbounded-pool requires cascade deletion. Remove --no-cascade to use it."
        )

    if args.cascade:
        cascade_body = {
            "loadbalancer": {
                "unbounded_pool": not bool(args.keep_unbounded_pool),
                "public_ip": not bool(args.keep_public_ip),
            }
        }
        if args.dry_run:
            print("Dry run request (cascade delete):")
            print(json.dumps(cascade_body, indent=2, ensure_ascii=False))
            return 0

        request_json(
            client,
            method="POST",
            resource_path=f"/v3/{project_id}/elb/loadbalancers/{loadbalancer_id}/delete-cascade",
            body=cascade_body,
        )
        print("Delete request accepted (cascade).")
        return 0

    if args.dry_run:
        print("Dry run request (delete):")
        print(json.dumps({"loadbalancer_id": loadbalancer_id}, indent=2, ensure_ascii=False))
        return 0

    request_json(
        client,
        method="DELETE",
        resource_path=f"/v3/{project_id}/elb/loadbalancers/{loadbalancer_id}",
        body=None,
    )
    print("Delete request accepted.")
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
