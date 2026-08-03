from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
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

from huawei_scope import CCE_ENDPOINT_TEMPLATE, CCE_NODE_CREATE_SCOPE_SECTION, DEFAULT_SCOPE_PATH


SCOPE_SECTION = CCE_NODE_CREATE_SCOPE_SECTION


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
    endpoint = f"https://{CCE_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    credentials = BasicCredentials(ak, sk, project_id) if project_id else BasicCredentials(ak, sk)
    return (
        ClientBuilder(CustomClient)
        .with_credentials(credentials)
        .with_region(Region(id=region, endpoint=endpoint))
        .build()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create Huawei Cloud CCE nodes with a standalone script.",
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
        help="Override the project_id from the scope file.",
    )
    parser.add_argument(
        "--cluster-id",
        help="Target CCE cluster ID.",
    )
    parser.add_argument("--name", help="Set metadata.name for the created node.")
    parser.add_argument(
        "--count",
        type=int,
        help="Number of nodes to create. Defaults to cce_node_create.node.spec.count or 1.",
    )
    parser.add_argument("--flavor", help="Set spec.flavor.")
    parser.add_argument("--az", help="Set spec.az, for example random.")
    parser.add_argument("--os", dest="os_name", help="Set spec.os.")
    parser.add_argument("--ssh-key", help="Use an SSH key pair for node login.")
    parser.add_argument(
        "--password-env",
        help="Read the node login password from this environment variable.",
    )
    parser.add_argument(
        "--username",
        help="Username for password login. Defaults to root when --password-env is used.",
    )
    parser.add_argument(
        "--root-volume-size",
        type=int,
        help="Set spec.rootVolume.size in GB.",
    )
    parser.add_argument(
        "--root-volume-type",
        help="Set spec.rootVolume.volumetype, for example SSD.",
    )
    parser.add_argument(
        "--data-volume",
        action="append",
        metavar="SIZE:TYPE",
        help="Replace spec.dataVolumes with one data disk. Repeat for more disks.",
    )
    parser.add_argument(
        "--subnet-id",
        help="Set spec.nodeNicSpec.primaryNic.subnetId.",
    )
    parser.add_argument(
        "--runtime",
        choices=("docker", "containerd"),
        help="Set spec.runtime.name.",
    )
    parser.add_argument(
        "--billing-mode",
        type=int,
        help="Set spec.billingMode.",
    )
    parser.add_argument(
        "--nodepool-scale-up",
        action="store_true",
        help="Send nodepoolScaleUp=NodepoolScaleUp in query parameters.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved request and exit without sending it.",
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


def cleaned_str(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_int(value: Any, *, field: str, required: bool = False) -> int | None:
    if value in (None, ""):
        if required:
            raise ValueError(f"Missing {field}.")
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer.") from exc


def normalize_scope_bool(value: Any, *, field: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    cleaned = cleaned_str(value).lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value for {field}: {value}")


def ensure_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")
    return value


def ensure_child_mapping(
    parent: dict[str, Any],
    key: str,
    *,
    field: str,
) -> dict[str, Any]:
    value = parent.get(key)
    if value is None:
        value = {}
        parent[key] = value
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object.")
    return value


def resolve_action_defaults(scope_config: dict[str, Any]) -> dict[str, Any]:
    section = scope_config.get(SCOPE_SECTION) or {}
    if not isinstance(section, dict):
        raise ValueError(f"Scope section '{SCOPE_SECTION}' must be an object.")

    node = section.get("node") or {}
    if not isinstance(node, dict):
        raise ValueError(f"Scope '{SCOPE_SECTION}.node' must be an object.")

    nodepool_scale_up = section.get("nodepool_scale_up")
    if nodepool_scale_up is None:
        nodepool_scale_up = section.get("nodepoolScaleUp")

    defaults: dict[str, Any] = {
        "region": section.get("region") or scope_config.get("region"),
        "project_id": section.get("project_id") or scope_config.get("project_id"),
        "cluster_id": section.get("cluster_id") or scope_config.get("cluster_id"),
        "node": node,
        "nodepool_scale_up": normalize_scope_bool(
            nodepool_scale_up,
            field=f"{SCOPE_SECTION}.nodepool_scale_up",
        ),
    }
    return defaults


def parse_data_volume_arg(raw_value: str) -> dict[str, Any]:
    parts = [part.strip() for part in raw_value.split(":")]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("--data-volume must use SIZE:TYPE, for example 100:SSD.")

    size = normalize_int(parts[0], field="data volume size", required=True)
    if size is None or size < 1:
        raise ValueError("data volume size must be greater than or equal to 1.")

    return {"size": size, "volumetype": parts[1]}


def parse_data_volume_args(raw_values: Sequence[str] | None) -> list[dict[str, Any]]:
    return [parse_data_volume_arg(raw_value) for raw_value in raw_values or []]


def apply_cli_overrides(
    node: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    node = deepcopy(node)
    node.setdefault("kind", "Node")
    node.setdefault("apiVersion", "v3")

    spec = ensure_child_mapping(node, "spec", field="node.spec")

    if args.name:
        metadata = ensure_child_mapping(node, "metadata", field="node.metadata")
        metadata["name"] = args.name
    if args.count is not None:
        spec["count"] = args.count
    if args.flavor:
        spec["flavor"] = args.flavor
    if args.az:
        spec["az"] = args.az
    if args.os_name:
        spec["os"] = args.os_name
    if args.runtime:
        spec["runtime"] = {"name": args.runtime}
    if args.billing_mode is not None:
        spec["billingMode"] = args.billing_mode

    if args.ssh_key and args.password_env:
        raise ValueError("--ssh-key and --password-env cannot be used together.")
    if args.ssh_key:
        spec["login"] = {"sshKey": args.ssh_key}
    if args.password_env:
        password = os.environ.get(args.password_env)
        if not password:
            raise ValueError(
                f"Environment variable '{args.password_env}' is missing or empty."
            )
        existing_login = spec.get("login") if isinstance(spec.get("login"), dict) else {}
        existing_password = (
            existing_login.get("userPassword")
            if isinstance(existing_login, dict)
            and isinstance(existing_login.get("userPassword"), dict)
            else {}
        )
        username = args.username or cleaned_str(existing_password.get("username")) or "root"
        spec["login"] = {
            "userPassword": {
                "username": username,
                "password": password,
            }
        }
    elif args.username:
        login = ensure_child_mapping(spec, "login", field="node.spec.login")
        user_password = login.get("userPassword")
        if not isinstance(user_password, dict):
            raise ValueError(
                "--username requires --password-env or an existing spec.login.userPassword object."
            )
        user_password["username"] = args.username

    if args.root_volume_size is not None or args.root_volume_type:
        root_volume = ensure_child_mapping(
            spec,
            "rootVolume",
            field="node.spec.rootVolume",
        )
        if args.root_volume_size is not None:
            root_volume["size"] = args.root_volume_size
        if args.root_volume_type:
            root_volume["volumetype"] = args.root_volume_type

    if args.data_volume:
        spec["dataVolumes"] = parse_data_volume_args(args.data_volume)

    if args.subnet_id:
        node_nic_spec = ensure_child_mapping(
            spec,
            "nodeNicSpec",
            field="node.spec.nodeNicSpec",
        )
        primary_nic = ensure_child_mapping(
            node_nic_spec,
            "primaryNic",
            field="node.spec.nodeNicSpec.primaryNic",
        )
        primary_nic["subnetId"] = args.subnet_id

    return node


def validate_volume(volume: Any, *, field: str) -> None:
    if not isinstance(volume, dict):
        raise ValueError(f"{field} must be an object.")

    size = normalize_int(volume.get("size"), field=f"{field}.size", required=True)
    if size is None or size < 1:
        raise ValueError(f"{field}.size must be greater than or equal to 1.")
    volume["size"] = size

    if not cleaned_str(volume.get("volumetype")):
        raise ValueError(f"Missing {field}.volumetype.")


def validate_login(login: Any) -> None:
    if not isinstance(login, dict):
        raise ValueError("node.spec.login must be an object.")

    ssh_key = cleaned_str(login.get("sshKey"))
    user_password = login.get("userPassword")
    has_user_password = False

    if user_password is not None:
        if not isinstance(user_password, dict):
            raise ValueError("node.spec.login.userPassword must be an object.")
        password = cleaned_str(user_password.get("password"))
        has_user_password = bool(password)
        if has_user_password and not cleaned_str(user_password.get("username")):
            user_password["username"] = "root"

    if ssh_key and has_user_password:
        raise ValueError("Use only one login method: sshKey or userPassword.")
    if not ssh_key and not has_user_password:
        raise ValueError("node.spec.login must provide sshKey or userPassword.password.")


def validate_request_body(node: dict[str, Any]) -> None:
    if cleaned_str(node.get("kind")) != "Node":
        raise ValueError("node.kind must be Node.")
    if cleaned_str(node.get("apiVersion")) != "v3":
        raise ValueError("node.apiVersion must be v3.")

    metadata = node.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ValueError("node.metadata must be an object.")
        if "name" in metadata:
            name = cleaned_str(metadata.get("name"))
            if not name:
                raise ValueError("node.metadata.name cannot be empty.")
            if len(name) > 56:
                raise ValueError("node.metadata.name cannot exceed 56 characters.")

    spec = ensure_mapping(node.get("spec"), field="node.spec")

    count = normalize_int(spec.get("count", 1), field="node.spec.count", required=True)
    if count is None or count < 1:
        raise ValueError("node.spec.count must be greater than or equal to 1.")
    spec["count"] = count

    billing_mode = normalize_int(spec.get("billingMode"), field="node.spec.billingMode")
    if billing_mode is not None:
        spec["billingMode"] = billing_mode

    if not cleaned_str(spec.get("flavor")):
        raise ValueError("Missing node.spec.flavor.")
    if not cleaned_str(spec.get("az")):
        raise ValueError("Missing node.spec.az.")

    validate_login(spec.get("login"))
    validate_volume(spec.get("rootVolume"), field="node.spec.rootVolume")

    data_volumes = spec.get("dataVolumes")
    if not isinstance(data_volumes, list) or not data_volumes:
        raise ValueError("node.spec.dataVolumes must be a non-empty list.")
    for index, data_volume in enumerate(data_volumes):
        validate_volume(data_volume, field=f"node.spec.dataVolumes[{index}]")


def build_query_params(
    args: argparse.Namespace,
    action_defaults: dict[str, Any],
) -> dict[str, Any]:
    nodepool_scale_up = bool(args.nodepool_scale_up)
    if not nodepool_scale_up and action_defaults.get("nodepool_scale_up") is not None:
        nodepool_scale_up = bool(action_defaults["nodepool_scale_up"])

    if not nodepool_scale_up:
        return {}
    return {"nodepoolScaleUp": "NodepoolScaleUp"}


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            if key == "password":
                redacted[key] = "******"
            else:
                redacted[key] = redact_secrets(child)
        return redacted
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value


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


def create_node(
    client,
    *,
    project_id: str,
    cluster_id: str,
    query_params: dict[str, Any],
    request_body: dict[str, Any],
) -> dict[str, Any]:
    return request_json(
        client,
        method="POST",
        resource_path=f"/api/v3/projects/{project_id}/clusters/{cluster_id}/nodes",
        query_params=query_params,
        body=request_body,
    )


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

    action_defaults = resolve_action_defaults(scope_config)
    region = args.region or action_defaults.get("region")
    project_id = args.project_id or action_defaults.get("project_id")
    cluster_id = args.cluster_id or action_defaults.get("cluster_id")
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")
    if not project_id:
        raise ValueError("Missing project_id. Set it in the scope file or pass --project-id.")
    if not cluster_id:
        raise ValueError("Missing cluster_id. Set it in the scope file or pass --cluster-id.")

    node = apply_cli_overrides(action_defaults["node"], args)
    validate_request_body(node)
    query_params = build_query_params(args, action_defaults)
    resource_path = f"/api/v3/projects/{project_id}/clusters/{cluster_id}/nodes"

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print(f"Cluster ID: {cluster_id}")
    print(f"Node Count: {node['spec']['count']}")
    metadata = node.get("metadata")
    if isinstance(metadata, dict) and cleaned_str(metadata.get("name")):
        print(f"Node Name: {metadata['name']}")

    if args.dry_run:
        print("Dry run request:")
        print(
            json.dumps(
                {
                    "method": "POST",
                    "resource_path": resource_path,
                    "query_params": query_params,
                    "body": redact_secrets(node),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    client = create_api_client(ak, sk, region, project_id=project_id)
    response_data = create_node(
        client,
        project_id=project_id,
        cluster_id=cluster_id,
        query_params=query_params,
        request_body=node,
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
