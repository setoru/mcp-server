## Runtime fallback when required tools are unavailable

If the expected <PRIMARY_SERVICE> MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local <PRIMARY_SERVICE> execution path is available, using one of:

- `huaweicloud_services_server/mcp_server_<service>/src/mcp_server_<service>/run.py`
- `huaweicloud_services_server/mcp_server_<service>/src/mcp_server_<service>/config/config.yaml`
- `huaweicloud_services_server/mcp_server_<service>/src/mcp_server_<service>/config/<service>.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

If the full service path is invalid or unavailable but a matching `*_lite` service safely exposes the same operation, that `*_lite` path is also allowed:

- `huaweicloud_services_server/mcp_server_<service>_lite/src/mcp_server_<service>_lite/run.py`
- `huaweicloud_services_server/mcp_server_<service>_lite/src/mcp_server_<service>_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_<service>_lite/src/mcp_server_<service>_lite/config/<service>.json`

When one of those repo-local specs is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker.

If this skill depends on auxiliary services such as <AUX_SERVICES>, list the exact auxiliary helper paths here too, or state clearly that the skill blocks when those auxiliary helper paths are unavailable.

Only report a blocker when neither the active MCP tool surface nor the repo-local fallback path can safely provide the required capability.
