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


IAM_ENDPOINT_TEMPLATE = "iam.{region}.myhuaweicloud.com"


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
            header_params.pop(self._CONTENT_TYPE, None)
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

            request_body = body

        sdk_request = SdkRequest(
            method=method,
            schema=schema,
            host=host,
            resource_path=resource_path,
            query_params=query_params,
            header_params=header_params,
            body=request_body,
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
    endpoint = f"https://{IAM_ENDPOINT_TEMPLATE.replace('{region}', region)}"
    # For IAM itself, do NOT pass a project_id here. We are querying it.
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
        body=None,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query Huawei Cloud region -> project_id mapping using IAM /v3/projects?name=<region>.",
    )
    parser.add_argument(
        "--scope",
        default=str(DEFAULT_SCOPE_PATH),
        help="Path to the Huawei scope YAML file.",
    )
    parser.add_argument(
        "--region",
        action="append",
        help="Region to query (repeatable). Defaults to scope region if not set.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print request parameters without sending the request.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print raw IAM response JSON per region.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Query all IAM-known regions (SDK built-in list).",
    )
    return parser


def infer_known_regions() -> list[str]:
    # Reuse the SDK's IAM endpoint region list, which should include regions that
    # have an IAM endpoint mapping.
    import huaweicloudsdkcore.auth.endpoint as endpoint_mod

    region_ids = getattr(endpoint_mod, "__IAM_ENDPOINT_DICT", {}).keys()
    return sorted(region_ids)


def query_projects_for_region(
    client,
    *,
    region: str,
) -> dict[str, Any]:
    response = request_json(
        client,
        method="GET",
        resource_path="/v3/projects",
        query_params={"name": region},
    )
    if not isinstance(response, dict):
        raise ValueError("Unexpected IAM response: expected an object.")
    return response


def extract_single_project_id(response: dict[str, Any]) -> str | None:
    projects = response.get("projects")
    if not isinstance(projects, list) or not projects:
        return None
    if len(projects) != 1:
        return None
    first = projects[0]
    if not isinstance(first, dict):
        return None
    return cleaned_str(first.get("id"))


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

    scope_region = cleaned_str(scope_config.get("region"))

    regions: list[str] = []
    if args.all:
        regions = infer_known_regions()
    if args.region:
        for item in args.region:
            cleaned = cleaned_str(item)
            if cleaned:
                regions.append(cleaned)
    if not regions and scope_region:
        regions = [scope_region]
    if not regions:
        raise ValueError("No regions provided. Pass --region or set region in the scope file.")

    print("Action: query-project-id")
    print(f"Scope: {scope_path}")
    print(f"Regions: {', '.join(regions)}")

    if args.dry_run:
        print("Dry run request:")
        print(
            json.dumps(
                {
                    "endpoint_template": IAM_ENDPOINT_TEMPLATE,
                    "method": "GET",
                    "resource_path": "/v3/projects",
                    "query_params": {"name": "<region>"},
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.json_output:
        raw_results: dict[str, Any] = {}
        for region in regions:
            client = create_api_client(ak, sk, region)
            raw_results[region] = query_projects_for_region(client, region=region)
        print(json.dumps(raw_results, indent=2, ensure_ascii=False))
        return 0

    for region in regions:
        client = create_api_client(ak, sk, region)
        response = query_projects_for_region(client, region=region)
        project_id = extract_single_project_id(response)
        if project_id:
            print(f"{region}: {project_id}")
        else:
            print(f"{region}: <not found or multiple; re-run with --json-output>")
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
