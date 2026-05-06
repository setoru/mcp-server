from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote

import yaml
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.client import Client, ClientBuilder
from huaweicloudsdkcore.exceptions.exceptions import HostUnreachableException
from huaweicloudsdkcore.region.region import Region
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.sdk_response import FutureSdkResponse
from huaweicloudsdkcore.utils import http_utils

from huawei_scope import DEFAULT_SCOPE_PATH


SWR_ENDPOINT_TEMPLATE = "swr-api.{region}.myhuaweicloud.com"
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


def create_api_client(ak: str, sk: str, region: str):
    endpoint = f"https://{SWR_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    credentials = BasicCredentials(ak, sk)
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
) -> Any:
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


def safe_get_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    return str(value).strip() if value not in (None, "") else "-"


def truncate(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    return value[: max(0, max_len - 3)] + "..."


def swr_path_repository_name(repository: str) -> str:
    # Huawei SWR API path parameters use '$' for multi-level repository names.
    # Example: "a/b" -> "a$b"
    return repository.replace("/", "$")


def print_repo_list(repos: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(repos, indent=2, ensure_ascii=False))
        return

    if not repos:
        print("No repositories found.")
        return

    for index, repo in enumerate(repos, start=1):
        description = safe_get_str(repo, "description")
        if description != "-":
            # Keep list output one-line, even if description contains newlines.
            description = " ".join(description.split())
            description = truncate(description, 80)
        print(
            f"{index}. {safe_get_str(repo, 'namespace')}/{safe_get_str(repo, 'name')} | "
            f"public={safe_get_str(repo, 'is_public')} | "
            f"images={safe_get_str(repo, 'num_images')} | "
            f"updated={safe_get_str(repo, 'updated_at')} | "
            f"desc={description}"
        )


def print_repo_detail(
    repo: dict[str, Any],
    *,
    namespace: str | None,
    as_json: bool,
) -> None:
    if as_json:
        print(json.dumps(repo, indent=2, ensure_ascii=False))
        return

    name = safe_get_str(repo, "name")
    ns = namespace or safe_get_str(repo, "namespace")
    print(f"Repository: {ns}/{name}")
    print(f"Description: {safe_get_str(repo, 'description')}")
    print(f"Public: {safe_get_str(repo, 'is_public')}")
    print(f"Images: {safe_get_str(repo, 'num_images')}")
    print(f"Downloads: {safe_get_str(repo, 'num_download')}")
    print(f"Size: {safe_get_str(repo, 'size')}")
    print(f"Category: {safe_get_str(repo, 'category')}")
    print(f"Path: {safe_get_str(repo, 'path')}")
    print(f"Internal Path: {safe_get_str(repo, 'internal_path')}")
    print(f"Created: {safe_get_str(repo, 'created')}")
    print(f"Updated: {safe_get_str(repo, 'updated')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Huawei Cloud SWR repositories (list and show details).",
    )
    parser.add_argument("action", choices=("list", "show"))
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument("--region", help="Override the region from the scope file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print request parameters without sending the request.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full results as JSON.",
    )

    # list filters
    parser.add_argument("--namespace", help="Filter by namespace (organization).")
    parser.add_argument("--name", help="Filter by repository name.")
    parser.add_argument(
        "--category",
        help="Filter by repository category, e.g. linux/framework_app/other.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help="Maximum number of repositories to query. Default is 1000.",
    )
    parser.add_argument("--offset", type=int, help="Query offset for pagination.")
    parser.add_argument("--order-column", dest="order_column", help="Sort column.")
    parser.add_argument(
        "--order-type",
        dest="order_type",
        choices=("asc", "desc"),
        help="Sort order.",
    )
    parser.add_argument(
        "--filter",
        dest="filter_expr",
        help="Raw filter expression supported by SWR API.",
    )

    # show args
    parser.add_argument(
        "--repository",
        help="Repository name for show action (requires --namespace).",
    )

    return parser


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

    region = args.region or cleaned_str(scope_config.get("region"))
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")

    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    client = create_api_client(ak, sk, region)

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")

    if args.action == "list":
        query_params: dict[str, Any] = {"limit": str(args.limit)}
        if args.namespace:
            query_params["namespace"] = args.namespace
        if args.name:
            query_params["name"] = args.name
        if args.category:
            query_params["category"] = args.category
        if args.offset is not None:
            if args.offset < 0:
                raise ValueError("--offset must be greater than or equal to 0.")
            query_params["offset"] = str(args.offset)
        if args.order_column:
            query_params["order_column"] = args.order_column
        if args.order_type:
            query_params["order_type"] = args.order_type
        if args.filter_expr:
            query_params["filter"] = args.filter_expr

        if args.dry_run:
            print("Dry run query params:")
            print(json.dumps(query_params, indent=2, ensure_ascii=False))
            return 0

        response_data = request_json(
            client,
            method="GET",
            resource_path="/v2/manage/repos",
            query_params=query_params,
        )
        if not isinstance(response_data, list):
            raise ValueError("Unexpected SWR response: expected a list.")
        print(f"Repo Count: {len(response_data)}")
        print_repo_list(response_data, as_json=args.json_output)
        return 0

    # show
    namespace = cleaned_str(args.namespace)
    repository = cleaned_str(args.repository)
    if not namespace:
        raise ValueError("--namespace is required for show action.")
    if not repository:
        raise ValueError("--repository is required for show action.")

    if args.dry_run:
        path_repository = swr_path_repository_name(repository)
        encoded_namespace = quote(namespace, safe="")
        encoded_repository = quote(path_repository, safe="")
        print("Dry run request:")
        print(
            json.dumps(
                {
                    "resource_path": f"/v2/manage/namespaces/{encoded_namespace}/repos/{encoded_repository}",
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    path_repository = swr_path_repository_name(repository)
    encoded_namespace = quote(namespace, safe="")
    encoded_repository = quote(path_repository, safe="")
    response_data = request_json(
        client,
        method="GET",
        resource_path=f"/v2/manage/namespaces/{encoded_namespace}/repos/{encoded_repository}",
    )
    if not isinstance(response_data, dict):
        raise ValueError("Unexpected SWR response: expected an object.")
    print_repo_detail(response_data, namespace=namespace, as_json=args.json_output)
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
