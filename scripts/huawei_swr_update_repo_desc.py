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
    endpoint = f"https://{SWR_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    # Prefer explicit project_id when available to avoid an extra IAM lookup.
    # BasicCredentials without project_id triggers an IAM /v3/projects call.
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


def swr_path_repository_name(repository: str) -> str:
    # Huawei SWR API path parameters use '$' for multi-level repository names.
    # Example: "a/b" -> "a$b"
    return repository.replace("/", "$")


def resolve_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        raise ValueError("Missing required boolean value.")
    cleaned = str(value).strip().lower()
    if cleaned in {"1", "true", "yes", "on"}:
        return True
    if cleaned in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Update Huawei Cloud SWR repository description (PATCH UpdateRepo).",
    )
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument("--region", help="Override the region from the scope file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved request without sending it.",
    )

    parser.add_argument("--namespace", required=True, help="SWR namespace (org).")
    parser.add_argument(
        "--repository",
        required=True,
        help="Repository name (supports multi-level names like a/b/c).",
    )
    desc_group = parser.add_mutually_exclusive_group(required=True)
    desc_group.add_argument(
        "--description",
        help="New repository description.",
    )
    desc_group.add_argument(
        "--description-file",
        dest="description_file",
        help="Read new repository description from a UTF-8 text file (keeps newlines).",
    )
    desc_group.add_argument(
        "--description-stdin",
        dest="description_stdin",
        action="store_true",
        help="Read new repository description from STDIN (keeps newlines).",
    )
    parser.add_argument(
        "--category",
        help="Optionally update repository category too (defaults to keeping current).",
    )

    public_group = parser.add_mutually_exclusive_group()
    public_group.add_argument(
        "--public",
        dest="is_public",
        action="store_true",
        default=None,
        help="Set repository to public.",
    )
    public_group.add_argument(
        "--private",
        dest="is_public",
        action="store_false",
        default=None,
        help="Set repository to private.",
    )

    return parser


def get_repo_detail(client, *, namespace: str, repository: str) -> dict[str, Any]:
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
    return response_data


def update_repo(
    client,
    *,
    namespace: str,
    repository: str,
    description: str,
    category: str | None,
    is_public: bool,
) -> Any:
    path_repository = swr_path_repository_name(repository)
    encoded_namespace = quote(namespace, safe="")
    encoded_repository = quote(path_repository, safe="")

    body: dict[str, Any] = {"description": description, "is_public": is_public}
    if category:
        body["category"] = category

    return request_json(
        client,
        method="PATCH",
        resource_path=f"/v2/manage/namespaces/{encoded_namespace}/repos/{encoded_repository}",
        body=body,
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

    region = args.region or cleaned_str(scope_config.get("region"))
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")

    namespace = cleaned_str(args.namespace)
    repository = cleaned_str(args.repository)
    if not namespace:
        raise ValueError("--namespace must not be empty.")
    if not repository:
        raise ValueError("--repository must not be empty.")

    if args.description_stdin:
        description = sys.stdin.read()
    elif args.description_file:
        desc_path = Path(args.description_file).expanduser()
        if not desc_path.exists():
            raise FileNotFoundError(f"Description file not found: {desc_path}")
        description = desc_path.read_text(encoding="utf-8-sig")
    else:
        description = str(args.description)

    project_id = cleaned_str(scope_config.get("project_id"))
    client = create_api_client(ak, sk, region, project_id=project_id)

    print("Action: update-desc")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Repository: {namespace}/{repository}")

    current_repo = get_repo_detail(client, namespace=namespace, repository=repository)
    current_is_public = resolve_bool(current_repo.get("is_public"))
    current_category = cleaned_str(current_repo.get("category"))
    current_desc = current_repo.get("description", "")

    effective_is_public = current_is_public if args.is_public is None else bool(args.is_public)
    effective_category = cleaned_str(args.category) or current_category

    print(f"Current: is_public={str(current_is_public).lower()} category={current_category or '-'}")
    print(f"Current Description: {current_desc if current_desc not in (None, '') else '-'}")
    print(f"New: is_public={str(effective_is_public).lower()} category={effective_category or '-'}")
    print("New Description:")
    print(description)

    request_body: dict[str, Any] = {
        "description": description,
        "is_public": effective_is_public,
    }
    if effective_category:
        request_body["category"] = effective_category

    if args.dry_run:
        path_repository = swr_path_repository_name(repository)
        encoded_namespace = quote(namespace, safe="")
        encoded_repository = quote(path_repository, safe="")
        print("Dry run request:")
        print(
            json.dumps(
                {
                    "method": "PATCH",
                    "resource_path": f"/v2/manage/namespaces/{encoded_namespace}/repos/{encoded_repository}",
                    "body": request_body,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    response_data = update_repo(
        client,
        namespace=namespace,
        repository=repository,
        description=description,
        category=effective_category,
        is_public=effective_is_public,
    )

    if response_data not in ({}, None, ""):
        # Docs say no response body, but keep this in case Huawei changes it.
        print("Response:")
        print(json.dumps(response_data, indent=2, ensure_ascii=False))
    else:
        print("Update request sent successfully.")

    updated_repo = get_repo_detail(client, namespace=namespace, repository=repository)
    print("After:")
    print(f"Description: {updated_repo.get('description') or '-'}")
    print(f"is_public: {str(resolve_bool(updated_repo.get('is_public'))).lower()}")
    print(f"category: {cleaned_str(updated_repo.get('category')) or '-'}")
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
