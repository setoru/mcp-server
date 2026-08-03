from __future__ import annotations

from pathlib import Path

# Centralized defaults used by the standalone Huawei Cloud scripts in this folder.
#
# Endpoint templates, list-page sizes, scope-section names and other shared
# defaults live here so they only need to be changed once. Individual scripts
# import what they need from this module instead of redefining copies.

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCOPE_PATH = REPO_ROOT / ".opencode" / "huawei-scope-2.yaml"

# --- Huawei Cloud service endpoint templates ---------------------------------
# Each value contains a literal "{region}" placeholder substituted at runtime.
CCE_ENDPOINT_TEMPLATE = "cce.{region}.myhuaweicloud.com"
ECS_ENDPOINT_TEMPLATE = "ecs.{region}.myhuaweicloud.com"
ELB_ENDPOINT_TEMPLATE = "elb.{region}.myhuaweicloud.com"
EVS_ENDPOINT_TEMPLATE = "evs.{region}.myhuaweicloud.com"
IAM_ENDPOINT_TEMPLATE = "iam.{region}.myhuaweicloud.com"
IMS_ENDPOINT_TEMPLATE = "ims.{region}.myhuaweicloud.com"
SWR_ENDPOINT_TEMPLATE = "swr-api.{region}.myhuaweicloud.com"
VPC_ENDPOINT_TEMPLATE = "vpc.{region}.myhuaweicloud.com"

# --- Shared numeric defaults -------------------------------------------------
DEFAULT_LIST_LIMIT = 1000
DEFAULT_LIST_LIMIT_VPC = 2000
DEFAULT_CREATE_COUNT = 1
DEFAULT_CHUNK_SIZE = 30000

# --- Naming / scope-section defaults -----------------------------------------
DEFAULT_RANDOM_NAME_PREFIX = "elb"
DEFAULT_NAMESPACE = "hwc-developer"
DEFAULT_REPOSITORY = "kruise-game-manager"
DEFAULT_EXPORT_ROOT = Path("C:/SWRDescriptionExports")

# Scope section name consumed by cce_node_create.
CCE_NODE_CREATE_SCOPE_SECTION = "cce_node_create"

# Scope section names consumed by the VPC security-group scripts.
VPC_SECURITY_GROUPS_SECTION = "vpc_security_groups"
VPC_SECURITY_GROUP_RULES_SECTION = "vpc_security_group_rules"
VPC_INGRESS_RULE_CREATE_SECTION = "vpc_ingress_rule_create"
VPC_INGRESS_RULE_UPDATE_SECTION = "vpc_ingress_rule_update"
VPC_INGRESS_RULE_DELETE_SECTION = "vpc_ingress_rule_delete"

# Defaults for VPC security-group rule operations.
DEFAULT_SG_DIRECTION = "ingress"
DEFAULT_SG_ETHERTYPE = "IPv4"
DEFAULT_SG_ACTION = "allow"
DEFAULT_SG_PROTOCOL = "tcp"
DEFAULT_SG_ENABLED = True
DEFAULT_SG_PRIORITY = 1

# --- request defaults --------------------------------------------------------
USER_AGENT = "huaweicloud-usdk-python/3.0"
REQUEST_TIMEOUT = (60, 120)

# EIP status sets used by the standalone EIP script.
EIP_IDLE_STATUSES = {"DOWN", "FREEZED", "ERROR"}
EIP_VALID_STATUSES = {"FREEZED", "DOWN", "ACTIVE", "ERROR"}
