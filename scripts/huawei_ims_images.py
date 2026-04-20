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


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCOPE_PATH = REPO_ROOT / ".opencode" / "huawei-scope-2.yaml"
IMS_ENDPOINT_TEMPLATE = "ims.{region}.myhuaweicloud.com"
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
    endpoint = f"https://{IMS_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    credentials = BasicCredentials(ak, sk)
    return (
        ClientBuilder(CustomClient)
        .with_credentials(credentials)
        .with_region(Region(id=region, endpoint=endpoint))
        .build()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Huawei Cloud IMS images (defaults to private images).",
    )
    parser.add_argument("action", choices=("list",))
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument("--region", help="Override the region from the scope file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print query parameters without sending the request.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Do not apply default private-image filters.",
    )
    parser.add_argument(
        "--imagetype",
        choices=("gold", "private", "shared", "market"),
        help="Filter by __imagetype. Defaults to private (unless --all).",
    )
    parser.add_argument(
        "--visibility",
        choices=("public", "private", "shared"),
        help="Filter by visibility. Defaults to private (unless --all).",
    )
    parser.add_argument("--id", help="Filter by image id.")
    parser.add_argument("--name", help="Filter by image name.")
    parser.add_argument("--status", help="Filter by image status, e.g. active.")
    parser.add_argument("--tag", help="Filter by a tag value.")
    parser.add_argument("--owner", help="Filter by owner (project id).")
    parser.add_argument(
        "--enterprise-project-id",
        dest="enterprise_project_id",
        help="Filter by enterprise project id.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIST_LIMIT,
        help="Maximum number of images to query. Default is 1000.",
    )
    parser.add_argument("--marker", help="Pagination marker.")
    parser.add_argument("--sort-key", dest="sort_key", help="Sort key.")
    parser.add_argument("--sort-dir", dest="sort_dir", choices=("asc", "desc"), help="Sort direction.")
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print full results as JSON.",
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


def request_json(
    client,
    *,
    method: str,
    resource_path: str,
    query_params: dict[str, Any] | None = None,
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
        body=None,
        response_headers=None,
    )
    return response.json() if response and response.content else {}


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_size_bytes(size_value: Any) -> str:
    size = parse_int(size_value)
    if size is None or size < 0:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)}{units[unit_index]}"
    return f"{value:.1f}{units[unit_index]}"


def safe_get_str(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    return str(value).strip() if value not in (None, "") else "-"


def print_image_list(images: list[dict[str, Any]], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(images, indent=2, ensure_ascii=False))
        return

    if not images:
        print("No images found.")
        return

    for index, image in enumerate(images, start=1):
        print(
            f"{index}. {safe_get_str(image, 'name')} | "
            f"id={safe_get_str(image, 'id')} | "
            f"status={safe_get_str(image, 'status')} | "
            f"imagetype={safe_get_str(image, '__imagetype')} | "
            f"visibility={safe_get_str(image, 'visibility')} | "
            f"os={safe_get_str(image, '__os_type')} {safe_get_str(image, '__platform')} {safe_get_str(image, '__os_version')} | "
            f"size={format_size_bytes(image.get('__image_size'))} | "
            f"created={safe_get_str(image, 'created_at')}"
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

    region = args.region or str(scope_config.get("region", "")).strip() or None
    if not region:
        raise ValueError("Missing region. Set it in the scope file or pass --region.")

    if args.limit < 1:
        raise ValueError("--limit must be greater than or equal to 1.")

    imagetype = args.imagetype
    visibility = args.visibility
    if not args.all:
        imagetype = imagetype or "private"
        visibility = visibility or "private"

    query_params: dict[str, Any] = {"limit": args.limit}
    if args.marker:
        query_params["marker"] = args.marker
    if imagetype:
        query_params["__imagetype"] = imagetype
    if visibility:
        query_params["visibility"] = visibility
    if args.id:
        query_params["id"] = args.id
    if args.name:
        query_params["name"] = args.name
    if args.status:
        query_params["status"] = args.status
    if args.tag:
        query_params["tag"] = args.tag
    if args.owner:
        query_params["owner"] = args.owner
    if args.enterprise_project_id:
        query_params["enterprise_project_id"] = args.enterprise_project_id
    if args.sort_key:
        query_params["sort_key"] = args.sort_key
    if args.sort_dir:
        query_params["sort_dir"] = args.sort_dir

    print(f"Action: {args.action}")
    print(f"Scope: {scope_path}")
    print(f"Region: {region}")
    print(f"Filters: __imagetype={imagetype or '-'} visibility={visibility or '-'} name={args.name or '-'} id={args.id or '-'}")

    if args.dry_run:
        print("Dry run query params:")
        print(json.dumps(query_params, indent=2, ensure_ascii=False))
        return 0

    client = create_api_client(ak, sk, region)
    response_data = request_json(
        client,
        method="GET",
        resource_path="/v2/cloudimages",
        query_params=query_params,
    )
    images = response_data.get("images", [])
    if not isinstance(images, list):
        raise ValueError("Unexpected IMS response: 'images' is not a list.")

    print(f"Image Count: {len(images)}")
    print_image_list(images, as_json=args.json_output)
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

