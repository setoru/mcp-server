from dataclasses import dataclass, field
from typing import Any, Optional, Literal

TransportType = Literal["sse", "stdio", "http"]


@dataclass
class MCPConfig:
    port: int
    service_code: str
    transport: TransportType
    ak: Optional[str] = None
    sk: Optional[str] = None
    default_region: Optional[str] = None
    default_project_id: Optional[str] = None
    default_enterprise_project_id: Optional[str] = None
    default_vpc_id: Optional[str] = None
    default_subnet_id: Optional[str] = None
    default_name: Optional[str] = None
    default_tool_arguments: dict[str, dict[str, Any]] = field(default_factory=dict)

    def check(self):
        if not self.service_code:
            raise ValueError("service_code必须已经初始化")

        if self.transport in ("sse", "http") and self.port == 0:
            raise ValueError("sse和http服务端口不能设为0")
