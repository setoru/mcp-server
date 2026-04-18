import json
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Union, get_args

import yaml
from huaweicloudsdkcore.auth.credentials import BasicCredentials
from huaweicloudsdkcore.client import Client, ClientBuilder
from huaweicloudsdkcore.exceptions.exceptions import HostUnreachableException
from huaweicloudsdkcore.http.http_config import HttpConfig
from huaweicloudsdkcore.region.region import Region
from huaweicloudsdkcore.sdk_request import SdkRequest
from huaweicloudsdkcore.sdk_response import FutureSdkResponse
from huaweicloudsdkcore.utils import http_utils

from .model import MCPConfig, TransportType
from .variable import (
    HUAWEI_ACCESS_KEY,
    HUAWEI_DEFAULT_REGION,
    HUAWEI_ENTERPRISE_PROJECT_ID,
    HUAWEI_RESOURCE_NAME,
    HUAWEI_SECRET_KEY,
    HUAWEI_SCOPE_FILE,
    HUAWEI_SUBNET_ID,
    HUAWEI_VPC_ID,
    MCP_SERVER_MODE,
    MCP_SERVER_PORT,
)


DEFAULT_SCOPE_FILE_NAME = "huawei-scope.yaml"
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
            except HostUnreachableException as e:
                with self._mutex:
                    if self._endpoint_index < len(self._endpoints) - 1:
                        self._endpoint_index += 1
                    else:
                        self._endpoint_index = 0
                        raise e

        return response


def create_api_client(ak, sk, x_host, region: str):
    endpoint = x_host

    if x_host.find("com") != -1:
        endpoint = f"https://{x_host}"

    if endpoint.find("{region}") != -1:
        endpoint = endpoint.replace("{region}", region)

    credentials = BasicCredentials(ak, sk)

    http_config = HttpConfig()
    http_config.ignore_ssl_verification = True

    return (
        ClientBuilder(CustomClient)
        .with_credentials(credentials)
        .with_region(Region(id=region, endpoint=endpoint))
        .build()
    )


def resolve_service_host(openapi_spec: dict[str, Any]) -> str:
    info = openapi_spec.get("info", {}) if isinstance(openapi_spec, dict) else {}
    explicit_host = info.get("x-host")
    if explicit_host:
        return str(explicit_host)

    host_prefix = info.get("x-host_prefix")
    if host_prefix:
        return f"{host_prefix}.{{region}}.myhuaweicloud.com"

    raise KeyError("x-host")


def build_http_info(name, arguments, openapi_spec, mcp_tools):
    # 基于Path name找到调用的Tool
    invoked_tool = next((tool for tool in mcp_tools if tool.name == name), None)
    if not invoked_tool:
        raise Exception(f"MCP工具({name})未找到")
    method = openapi_spec.get("paths").get(f"/{name}").get("x-method")
    resource_path = (
        openapi_spec.get("paths").get(f"/{name}").get("x-url").replace("{endpoint}", "")
    )

    cname = None
    collection_formats = {}
    path_params = {}
    query_params = {}
    header_params = {}
    form_params = {}
    request_body = {}
    response_headers = None
    
    # 用于收集需要包装的参数
    wrapper_params = {}

    properties = invoked_tool.inputSchema.get("properties", {})
    for property_name, property_body in properties.items():
        # 跳过特殊参数（region用于选择endpoint，不发送到API）
        if property_name in ["X-Auth-Token", "region"]:
            continue
        elif (
            property_name in invoked_tool.inputSchema.get("required", [])
            and arguments.get(property_name) is None
        ):
            raise Exception(f"{property_name}为必填参数.")

        property_in = property_body.get("in")
        body_wrapper = property_body.get("_body_wrapper")
        
        if property_in == "query":
            query_params[property_name] = arguments.get(property_name)
        elif property_in == "path":
            path_params[property_name] = arguments.get(property_name)
        elif property_in == "header":
            header_params[property_name] = arguments.get(property_name)
        elif body_wrapper:
            # 这个参数需要被包装到指定的wrapper中
            if body_wrapper not in wrapper_params:
                wrapper_params[body_wrapper] = {}
            param_value = arguments.get(property_name)
            if param_value is not None:
                wrapper_params[body_wrapper][property_name] = param_value
        elif property_in is None:
            request_body[property_name] = arguments.get(property_name)
    
    # 将收集的wrapper参数添加到request_body
    for wrapper_name, wrapper_content in wrapper_params.items():
        if wrapper_content:  # 只有非空的wrapper才添加
            request_body[wrapper_name] = wrapper_content
            
    header_params["Content-Type"] = http_utils.select_header_content_type(
        ["application/json;charset=UTF-8"]
    )
    # 如果body为空则设为None（避免DELETE等方法发送空body报错）
    filtered_body = request_body or None
    http_info = {
        "method": method,
        "resource_path": resource_path,
        "cname": cname,
        "collection_formats": collection_formats,
        "path_params": path_params,
        "query_params": query_params,
        "header_params": header_params,
        "post_params": form_params,
        "body": filtered_body,
        "response_headers": response_headers,
    }

    return http_info


def load_openapi(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            result = json.load(file)
            return result
    except FileNotFoundError:
        raise FileNotFoundError(f"OpenAPI文件未找到: {config_path}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"无效的JSON格式: {str(e)}", e.doc, e.pos)
    except IOError as e:
        raise IOError(f"加载OpenAPI文件失败: {str(e)}")

def load_config(config_path: Union[str, Path]) -> MCPConfig:
    config_path = Path(config_path)
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f) or {}
    except FileNotFoundError:
        raise FileNotFoundError(f"YAML 文件未找到: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"无效的 YAML 格式: {e}")

    if not isinstance(config_dict, dict):
        raise ValueError("配置文件内容必须是对象映射")

    scope_defaults = _merge_scope_sources(
        _normalize_scope_config(config_dict.get("huawei_scope")),
        _load_scope_file(_get_user_scope_path()),
        _load_scope_file(_find_project_scope_path(config_path)),
    )

    # 创建主配置对象
    try:
        cfg = MCPConfig(
            service_code=config_dict.get("service_code", ""),
            transport=config_dict.get("transport", ""),
            port=config_dict.get("port", 8888),
            ak=scope_defaults.get("ak") or config_dict.get("ak", ""),
            sk=scope_defaults.get("sk") or config_dict.get("sk", ""),
            default_region=scope_defaults.get("region"),
            default_project_id=scope_defaults.get("project_id"),
            default_enterprise_project_id=scope_defaults.get("enterprise_project_id"),
            default_vpc_id=scope_defaults.get("vpc_id"),
            default_subnet_id=scope_defaults.get("subnet_id"),
            default_name=scope_defaults.get("name"),
            default_tool_arguments=_extract_tool_scope_defaults(scope_defaults),
        )

        env_mapping = [
            (HUAWEI_ACCESS_KEY, "ak", None, None),
            (HUAWEI_SECRET_KEY, "sk", None, None),
            (HUAWEI_DEFAULT_REGION, "default_region", None, None),
            (
                HUAWEI_ENTERPRISE_PROJECT_ID,
                "default_enterprise_project_id",
                None,
                None,
            ),
            (HUAWEI_VPC_ID, "default_vpc_id", None, None),
            (HUAWEI_SUBNET_ID, "default_subnet_id", None, None),
            (HUAWEI_RESOURCE_NAME, "default_name", None, None),
            (MCP_SERVER_MODE, "transport", None, get_args(TransportType)),
            (MCP_SERVER_PORT, "port", int, None),
        ]

        for env_var, attr_name, converter, allowed_values in env_mapping:
            env_value_str = os.environ.get(env_var)
            if env_value_str is not None and env_value_str != "":
                # 转换类型
                value_to_set = converter(env_value_str) if converter else env_value_str
                # 验证 Literal 类型的值
                if allowed_values is not None and value_to_set not in allowed_values:
                    raise ValueError(
                        f"无效值 '{value_to_set}'. 有效值清单: {allowed_values}"
                    )
                setattr(cfg, attr_name, value_to_set)
        # 参数校验
        cfg.check()
        return cfg
    except (ValueError, TypeError) as e:
        raise ValueError(f"读取配置文件时发生错误 {e}")


def filter_parameters(params_dict):
    """过滤参数，移除None值、空列表和特殊参数（如region）"""
    # 需要从请求中移除的特殊参数（这些参数用于路由而非API调用）
    special_params = {"region"}
    
    filtered_dict = {}
    for key, value in params_dict.items():
        # 跳过特殊参数
        if key in special_params:
            continue
        # 检查值是否不是 None 并且不是空列表
        if value is not None and not (isinstance(value, list) and not value):
            filtered_dict[key] = value
    return filtered_dict


def apply_default_scope(arguments: dict[str, Any] | None, invoked_tool, config: MCPConfig):
    """为工具调用补齐默认scope，仅在调用参数缺失且工具实际支持该字段时生效。"""
    scoped_arguments = dict(arguments or {})
    if invoked_tool is None:
        return scoped_arguments

    properties = getattr(invoked_tool, "inputSchema", {}).get("properties", {})
    tool_scope_defaults = _resolve_tool_scope_defaults(invoked_tool, config)
    if tool_scope_defaults:
        scoped_arguments = _merge_tool_arguments(
            scoped_arguments,
            tool_scope_defaults,
            properties,
        )

    default_mapping = {
        "region": config.default_region,
        "project_id": config.default_project_id,
        "enterprise_project_id": config.default_enterprise_project_id,
        "vpc_id": config.default_vpc_id,
        "subnet_id": config.default_subnet_id,
    }

    for field_name, default_value in default_mapping.items():
        if (
            default_value is not None
            and field_name in properties
            and scoped_arguments.get(field_name) in (None, "")
        ):
            scoped_arguments[field_name] = default_value

    if (
        "project_id" in properties
        and scoped_arguments.get("project_id") in (None, "")
        and scoped_arguments.get("region") not in (None, "")
        and config.ak
        and config.sk
    ):
        resolved_project_id = resolve_project_id_from_region(
            config.ak,
            config.sk,
            scoped_arguments["region"],
        )
        if resolved_project_id:
            scoped_arguments["project_id"] = resolved_project_id

    return scoped_arguments


def resolve_invocation_region(
    arguments: dict[str, Any] | None, config: MCPConfig
) -> str | None:
    scoped_arguments = arguments or {}
    region = scoped_arguments.get("region")
    if region in (None, ""):
        return config.default_region
    return str(region)


def resolve_project_id_from_region(ak: str, sk: str, region: str) -> str | None:
    projects = list_auth_projects(ak, sk, region)
    if not projects:
        return None

    exact_name_match = next(
        (
            project
            for project in projects
            if str(project.get("name", "")).lower() == region.lower()
        ),
        None,
    )
    selected_project = exact_name_match or projects[0]
    project_id = selected_project.get("id")
    return str(project_id) if project_id else None


def list_auth_projects(ak: str, sk: str, region: str) -> list[dict[str, Any]]:
    iam_client = create_api_client(ak, sk, IAM_ENDPOINT_TEMPLATE, region)
    response = iam_client.do_http_request(
        method="GET",
        resource_path="/v3/auth/projects",
        collection_formats={},
        path_params={},
        query_params={},
        header_params={
            "Content-Type": http_utils.select_header_content_type(
                ["application/json;charset=UTF-8"]
            )
        },
        post_params={},
        body=None,
        response_headers=None,
    )
    response_data = response.json() if response and response.content else {}
    projects = response_data.get("projects", [])
    return projects if isinstance(projects, list) else []


def _load_scope_file(scope_path: Path | None) -> dict[str, Any]:
    if scope_path is None or not scope_path.exists():
        return {}

    try:
        with open(scope_path, "r", encoding="utf-8") as f:
            scope_dict = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"无效的scope YAML格式 {scope_path}: {e}")

    return _normalize_scope_config(scope_dict)


def _normalize_scope_config(scope_dict: Any) -> dict[str, Any]:
    if not scope_dict:
        return {}
    if not isinstance(scope_dict, dict):
        raise ValueError("scope配置必须是对象映射")

    if isinstance(scope_dict.get("default"), dict):
        scope_dict = scope_dict["default"]

    normalized: dict[str, Any] = {}
    for key in (
        "ak",
        "sk",
        "region",
        "project_id",
        "enterprise_project_id",
        "vpc_id",
        "subnet_id",
        "name",
    ):
        value = scope_dict.get(key)
        if value not in (None, ""):
            normalized[key] = str(value)

    for key in (
        "ecs_list",
        "ecs_create",
        "ecs_delete",
        "ecs_stop",
        "nat_list",
        "nat_create_gateway",
        "nat_create_snat",
        "nat_delete",
        "elb_list",
        "elb_create",
        "elb_delete",
        "cce_list",
        "cce_create",
        "cce_hibernate",
        "cce_awake",
    ):
        value = scope_dict.get(key)
        if isinstance(value, dict) and value:
            normalized[key] = deepcopy(value)
    return normalized


def _merge_scope_sources(*scope_sources: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for scope_source in scope_sources:
        for key, value in scope_source.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = _deep_merge_defaults(merged[key], value)
            else:
                merged[key] = deepcopy(value)
    return merged


def _extract_tool_scope_defaults(scope_defaults: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: deepcopy(scope_defaults[key])
        for key in (
            "ecs_list",
            "ecs_create",
            "ecs_delete",
            "ecs_stop",
            "nat_list",
            "nat_create_gateway",
            "nat_create_snat",
            "nat_delete",
            "elb_list",
            "elb_create",
            "elb_delete",
            "cce_list",
            "cce_create",
            "cce_hibernate",
            "cce_awake",
        )
        if isinstance(scope_defaults.get(key), dict)
    }


def _resolve_tool_scope_defaults(invoked_tool, config: MCPConfig) -> dict[str, Any]:
    tool_name = getattr(invoked_tool, "name", "")
    tool_scope_map = {
        "huaweicloud-ecs_ListServersDetails": "ecs_list",
        "huaweicloud-ecs_ListCloudServers": "ecs_list",
        "huaweicloud-ecs_ShowServer": "ecs_list",
        "huaweicloud-ecs_CreateServers": "ecs_create",
        "huaweicloud-ecs_DeleteServers": "ecs_delete",
        "huaweicloud-ecs_BatchStopServers": "ecs_stop",
        "huaweicloud-nat_ListNatGateways": "nat_list",
        "huaweicloud-nat_CreateNatGateway": "nat_create_gateway",
        "huaweicloud-nat_CreateNatGatewaySnatRule": "nat_create_snat",
        "huaweicloud-nat_ListNatGatewaySnatRules": "nat_delete",
        "huaweicloud-nat_DeleteNatGatewaySnatRule": "nat_delete",
        "huaweicloud-nat_DeleteNatGateway": "nat_delete",
        "huaweicloud-elb_ListLoadbalancers": "elb_list",
        "huaweicloud-elb_ShowLoadBalancer": "elb_list",
        "huaweicloud-elb_CreateLoadbalancer": "elb_create",
        "huaweicloud-elb_DeleteLoadBalancer": "elb_delete",
        "huaweicloud-cce_ListClusters": "cce_list",
        "huaweicloud-cce_ShowCluster": "cce_list",
        "huaweicloud-cce_CreateCluster": "cce_create",
        "huaweicloud-cce_HibernateCluster": "cce_hibernate",
        "huaweicloud-cce_AwakeCluster": "cce_awake",
    }
    scope_key = tool_scope_map.get(tool_name)
    if not scope_key:
        return {}
    return deepcopy(config.default_tool_arguments.get(scope_key, {}))


def _merge_tool_arguments(
    explicit_arguments: dict[str, Any],
    default_arguments: dict[str, Any],
    properties: dict[str, Any],
) -> dict[str, Any]:
    merged_arguments = dict(explicit_arguments)
    for field_name, default_value in default_arguments.items():
        if field_name not in properties:
            continue
        explicit_value = merged_arguments.get(field_name)
        if explicit_value in (None, ""):
            merged_arguments[field_name] = deepcopy(default_value)
            continue
        if isinstance(explicit_value, dict) and isinstance(default_value, dict):
            merged_arguments[field_name] = _deep_merge_defaults(explicit_value, default_value)
    return merged_arguments


def _deep_merge_defaults(explicit_value: dict[str, Any], default_value: dict[str, Any]) -> dict[str, Any]:
    merged_value = deepcopy(default_value)
    for key, value in explicit_value.items():
        if isinstance(value, dict) and isinstance(merged_value.get(key), dict):
            merged_value[key] = _deep_merge_defaults(value, merged_value[key])
        else:
            merged_value[key] = deepcopy(value)
    return merged_value


def _find_project_scope_path(config_path: Path) -> Path | None:
    for parent in (config_path.resolve(), *config_path.resolve().parents):
        candidate = parent / ".opencode" / DEFAULT_SCOPE_FILE_NAME
        if candidate.exists():
            return candidate
    return None


def _get_user_scope_path() -> Path:
    override_path = os.environ.get(HUAWEI_SCOPE_FILE)
    if override_path:
        return Path(override_path).expanduser()

    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "mcp-server"
            / DEFAULT_SCOPE_FILE_NAME
        )

    if os.name == "nt":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / "mcp-server" / DEFAULT_SCOPE_FILE_NAME

    return Path.home() / ".config" / "mcp-server" / DEFAULT_SCOPE_FILE_NAME

