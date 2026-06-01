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


CCE_ENDPOINT_TEMPLATE = "cce.{region}.myhuaweicloud.com"
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
        description="List, awake, or hibernate Huawei Cloud CCE clusters with a standalone script.",
    )
    parser.add_argument("action", choices=("list", "awake", "hibernate"))
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
        "--dry-run",
        action="store_true",
        help="Resolve target clusters and print the request without sending it.",
    )
    parser.add_argument(
        "--detail",
        action="store_true",
        help="Query detailed CCE cluster information.",
    )
    parser.add_argument(
        "--status",
        help="Filter CCE list by status, for example Available or Hibernation.",
    )
    parser.add_argument(
        "--cluster-type",
        dest="cluster_type",
        help="Filter CCE list by type, for example VirtualMachine or ARM64.",
    )
    parser.add_argument(
        "--version",
        help="Filter CCE list by Kubernetes version, for example v1.33.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help="Maximum number of CCE records to query when listing. Default is 1000.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full CCE list results as JSON.",
    )
    parser.add_argument(
        "--all-name-matches",
        action="store_true",
        help="Allow multiple exact matches when selecting by --name.",
    )

    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--cluster-id",
        help="Target CCE cluster ID.",
    )
    target_group.add_argument(
        "--name",
        help="Exact CCE cluster name or alias to match.",
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


def resolve_action_defaults(scope_config: dict[str, Any], action: str) -> dict[str, Any]:
    section_name = f"cce_{action}"
    section = scope_config.get(section_name) or {}
    if not isinstance(section, dict):
        raise ValueError(f"Scope section '{section_name}' must be an object.")

    defaults = {
        "region": section.get("region") or scope_config.get("region"),
        "project_id": section.get("project_id") or scope_config.get("project_id"),
        "cluster_id": section.get("cluster_id") or scope_config.get("cluster_id"),
        "name": section.get("name"),
        "detail": normalize_scope_bool(section.get("detail")),
        "status": section.get("status"),
        "cluster_type": section.get("type"),
        "version": section.get("version"),
    }
    return defaults


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
    raise ValueError(f"Unsupported boolean value in scope: {value}")


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


def cluster_id_of(cluster: dict[str, Any]) -> str:
    metadata = cluster.get("metadata", {})
    if not isinstance(metadata, dict):
        return ""
    for key in ("uid", "id"):
        value = str(metadata.get(key, "")).strip()
        if value:
            return value
    return ""


def cluster_name_of(cluster: dict[str, Any]) -> str:
    metadata = cluster.get("metadata", {})
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("name", "")).strip()


def cluster_alias_of(cluster: dict[str, Any]) -> str:
    metadata = cluster.get("metadata", {})
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("alias", "")).strip()


def cluster_status_of(cluster: dict[str, Any]) -> str:
    status = cluster.get("status", {})
    if not isinstance(status, dict):
        return "UNKNOWN"
    value = str(status.get("phase", "")).strip()
    return value or "UNKNOWN"


def cluster_type_of(cluster: dict[str, Any]) -> str:
    spec = cluster.get("spec", {})
    if not isinstance(spec, dict):
        return "-"
    value = str(spec.get("type", "")).strip()
    return value or "-"


def cluster_version_of(cluster: dict[str, Any]) -> str:
    spec = cluster.get("spec", {})
    if not isinstance(spec, dict):
        return "-"
    value = str(spec.get("version", "")).strip()
    return value or "-"


def dedupe_clusters(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_clusters: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for cluster in clusters:
        cluster_id = cluster_id_of(cluster)
        if not cluster_id or cluster_id in seen_ids:
            continue
        seen_ids.add(cluster_id)
        unique_clusters.append(cluster)
    return unique_clusters


def list_clusters(
    client,
    *,
    project_id: str,
    detail: bool = False,
    status: str | None = None,
    cluster_type: str | None = None,
    version: str | None = None,
) -> list[dict[str, Any]]:
    query_params: dict[str, Any] = {}
    if detail:
        query_params["detail"] = "true"
    if status:
        query_params["status"] = status
    if cluster_type:
        query_params["type"] = cluster_type
    if version:
        query_params["version"] = version

    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/api/v3/projects/{project_id}/clusters",
        query_params=query_params,
    )
    clusters = response_data.get("items", [])
    if not isinstance(clusters, list):
        raise ValueError("Unexpected CCE list response: 'items' is not a list.")
    return clusters


def show_cluster(
    client,
    *,
    project_id: str,
    cluster_id: str,
    detail: bool = False,
) -> dict[str, Any]:
    query_params: dict[str, Any] = {}
    if detail:
        query_params["detail"] = "true"

    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/api/v3/projects/{project_id}/clusters/{cluster_id}",
        query_params=query_params,
    )
    if not isinstance(response_data, dict):
        raise ValueError("Unexpected CCE show response.")
    return response_data


def filter_clusters(
    clusters: list[dict[str, Any]],
    *,
    cluster_id: str | None = None,
    name: str | None = None,
) -> list[dict[str, Any]]:
    filtered = clusters

    if cluster_id:
        expected_id = cluster_id.strip()
        filtered = [
            cluster for cluster in filtered if cluster_id_of(cluster) == expected_id
        ]

    if name:
        expected_name = name.strip()
        filtered = [
            cluster
            for cluster in filtered
            if cluster_name_of(cluster) == expected_name
            or cluster_alias_of(cluster) == expected_name
        ]

    return dedupe_clusters(filtered)


def select_exact_name_matches(
    clusters: list[dict[str, Any]],
    expected_name: str,
    allow_multiple: bool = False,
) -> list[dict[str, Any]]:
    matches = filter_clusters(clusters, name=expected_name)
    if not matches:
        raise ValueError(f"No CCE cluster matched the exact name or alias '{expected_name}'.")
    if len(matches) > 1 and not allow_multiple:
        matched_ids = ", ".join(cluster_id_of(cluster) for cluster in matches)
        raise ValueError(
            "Multiple CCE clusters share that exact name or alias. "
            f"Use --cluster-id to disambiguate or pass --all-name-matches. Matched IDs: {matched_ids}"
        )
    return matches


def print_cluster_list(clusters: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(clusters, indent=2, ensure_ascii=False))
        return

    if not clusters:
        print("No CCE clusters found.")
        return

    for index, cluster in enumerate(clusters, start=1):
        alias = cluster_alias_of(cluster)
        alias_part = f" | alias={alias}" if alias else ""
        print(
            f"{index}. {cluster_name_of(cluster) or '<unknown>'} | "
            f"id={cluster_id_of(cluster)} | "
            f"status={cluster_status_of(cluster)} | "
            f"type={cluster_type_of(cluster)} | "
            f"version={cluster_version_of(cluster)}"
            f"{alias_part}"
        )


def hibernate_cluster(client, *, project_id: str, cluster_id: str) -> dict[str, Any]:
    return request_json(
        client,
        method="POST",
        resource_path=f"/api/v3/projects/{project_id}/clusters/{cluster_id}/operation/hibernate",
    )


def awake_cluster(client, *, project_id: str, cluster_id: str) -> dict[str, Any]:
    return request_json(
        client,
        method="POST",
        resource_path=f"/api/v3/projects/{project_id}/clusters/{cluster_id}/operation/awake",
    )


def resolve_target_clusters(
    client,
    *,
    project_id: str,
    detail: bool,
    cluster_id: str | None,
    name: str | None,
    allow_multiple: bool,
    allow_missing_cluster_fallback: bool = False,
    fallback_cluster_id: str | None = None,
) -> list[dict[str, Any]]:
    if cluster_id:
        try:
            cluster = show_cluster(
                client,
                project_id=project_id,
                cluster_id=cluster_id,
                detail=detail,
            )
            resolved_id = cluster_id_of(cluster)
            if not resolved_id:
                raise ValueError(f"Could not resolve CCE cluster: {cluster_id}")
            return [cluster]
        except Exception:
            if not allow_missing_cluster_fallback:
                raise

            if fallback_cluster_id and fallback_cluster_id != cluster_id:
                fallback_cluster = show_cluster(
                    client,
                    project_id=project_id,
                    cluster_id=fallback_cluster_id,
                    detail=detail,
                )
                resolved_id = cluster_id_of(fallback_cluster)
                if resolved_id:
                    return [fallback_cluster]

    all_clusters = dedupe_clusters(
        list_clusters(
            client,
            project_id=project_id,
            detail=detail,
        )
    )

    if name:
        return select_exact_name_matches(
            all_clusters,
            name,
            allow_multiple=allow_multiple,
        )

    if len(all_clusters) == 1:
        return all_clusters

    raise ValueError(
        "No target cluster provided. Pass --cluster-id or --name, configure cce_awake/cce_hibernate.cluster_id in the scope file, "
        "or keep only one CCE cluster in the selected project for automatic targeting."
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

    detail = args.detail
    if not args.detail and action_defaults.get("detail") is not None:
        detail = bool(action_defaults["detail"])

    cluster_id = args.cluster_id or action_defaults.get("cluster_id")
    cluster_name = args.name or action_defaults.get("name")
    status = args.status or action_defaults.get("status")
    cluster_type = args.cluster_type or action_defaults.get("cluster_type")
    version = args.version or action_defaults.get("version")
    top_level_cluster_id = str(scope_config.get("cluster_id", "")).strip() or None

    client = create_api_client(ak, sk, region, project_id=project_id)

    if args.action == "list":
        if cluster_id:
            queried_clusters = [
                show_cluster(
                    client,
                    project_id=project_id,
                    cluster_id=cluster_id,
                    detail=detail,
                )
            ]
        else:
            queried_clusters = dedupe_clusters(
                list_clusters(
                    client,
                    project_id=project_id,
                    detail=detail,
                    status=status,
                    cluster_type=cluster_type,
                    version=version,
                )
            )

        if cluster_name:
            queried_clusters = filter_clusters(
                queried_clusters,
                name=cluster_name,
            )

        if len(queried_clusters) > args.limit:
            queried_clusters = queried_clusters[: args.limit]

        print(f"Action: {args.action}")
        print(f"Scope: {scope_path}")
        print(f"Region: {region}")
        print(f"Project ID: {project_id}")
        print(f"CCE Count: {len(queried_clusters)}")
        print_cluster_list(queried_clusters, as_json=args.json_output)
        return 0

    target_clusters = resolve_target_clusters(
        client,
        project_id=project_id,
        detail=detail,
        cluster_id=cluster_id,
        name=cluster_name,
        allow_multiple=args.all_name_matches,
        allow_missing_cluster_fallback=(
            args.cluster_id is None
            and bool(top_level_cluster_id)
            and cluster_id not in (None, "", top_level_cluster_id)
        ),
        fallback_cluster_id=top_level_cluster_id,
    )

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Project ID: {project_id}")
    print("Targets:")
    for cluster in target_clusters:
        alias = cluster_alias_of(cluster)
        alias_part = f" alias={alias}" if alias else ""
        print(
            f"  - {cluster_name_of(cluster) or '<unknown>'} "
            f"({cluster_id_of(cluster)}) "
            f"status={cluster_status_of(cluster)}{alias_part}"
        )

    if args.dry_run:
        print("Dry run request:")
        print(
            json.dumps(
                {
                    "cluster_ids": [cluster_id_of(cluster) for cluster in target_clusters],
                    "action": args.action,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    responses: list[dict[str, Any]] = []
    for cluster in target_clusters:
        target_cluster_id = cluster_id_of(cluster)
        if args.action == "hibernate":
            response_data = hibernate_cluster(
                client,
                project_id=project_id,
                cluster_id=target_cluster_id,
            )
        else:
            response_data = awake_cluster(
                client,
                project_id=project_id,
                cluster_id=target_cluster_id,
            )

        responses.append(
            {
                "cluster_id": target_cluster_id,
                "name": cluster_name_of(cluster),
                "response": response_data,
            }
        )

    print("Response:")
    print(json.dumps(responses, indent=2, ensure_ascii=False))
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
