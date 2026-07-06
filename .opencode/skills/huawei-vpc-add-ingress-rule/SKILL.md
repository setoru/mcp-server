---
name: huawei-vpc-add-ingress-rule
description: Create one Huawei Cloud security group ingress rule through Huawei Cloud VPC MCP tools. Use when the user explicitly wants inbound access added and already knows the exact target security group, protocol, port scope, and remote peer.
compatibility: Prefers Huawei Cloud VPC MCP tools in the current environment. If they are unavailable but the repo-local VPC helper path is present, this skill may use that bounded fallback path instead. IAM MCP tools remain useful follow-ups for project discovery.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: add-ingress-rule
---

# Huawei VPC Add Ingress Rule

## What this skill does

- Create exactly one security group ingress rule.
- Fix the rule direction to inbound access only.
- Run a minimal preflight lookup on the target security group before creation.
- Report the result conservatively, especially when only request-stage acceptance is available.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the tool supports it and the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
The same scope file may also contain `name`, but that field is an AI-side fuzzy-match hint and must not be passed directly as an API filter unless it has already been normalized to an exact resource name.

Primary tools:

- `huaweicloud-vpc_ListSecurityGroups`
- `huaweicloud-vpc_CreateSecurityGroupRule`
- `huaweicloud-vpc_ShowSecurityGroupRule`

Useful follow-up tools when narrowing scope:

- `huaweicloud-iam_KeystoneListAuthProjects`
- `huaweicloud-iam_KeystoneListProjects`
- `huaweicloud-iam_KeystoneShowProject`

## Runtime fallback when required tools are unavailable

If the expected VPC MCP tools are not currently exposed in the active runtime, do not stop immediately. First check whether the repo-local VPC execution path is available, using one of:

- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/run.py`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/config/config.yaml`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/config/vpc.json`
- `huaweicloud_services_server/mcp_server_vpc_lite/src/mcp_server_vpc_lite/run.py`
- `huaweicloud_services_server/mcp_server_vpc_lite/src/mcp_server_vpc_lite/config/config.yaml`
- `huaweicloud_services_server/mcp_server_vpc_lite/src/mcp_server_vpc_lite/config/vpc.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When one of those repo-local VPC specs is present and valid for the required operation, this skill may use the repo-local OpenAPI execution chain to complete the same bounded workflow instead of declaring an immediate blocker. Only report a blocker when neither the active MCP tool surface nor the repo-local VPC execution path can safely provide the required capability.

## Required inputs

- `project_id` (or enough region context to discover it with IAM first)
- `security_group_id`
- `ethertype`
- `protocol`
- exactly one of `remote_ip_prefix`, `remote_group_id`, or `remote_address_group_id`

Conditionally required inputs:

- `multiport` when the chosen protocol uses ports, such as `tcp` or `udp`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `description`
- `action` (if omitted, treat `allow` as the expected explicit intent and say so before execution)
- `priority`
- `enabled`
- `dry_run`

## Default workflow

1. Treat this as the inbound access rule skill.
   - This skill creates ingress only.
   - Fix `direction` to `ingress`.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is missing, prefer discovering it with `huaweicloud-iam_KeystoneListAuthProjects({ region })` before continuing.
   - Do not silently mix a `project_id` from one region with a different `region`.

3. Require explicit target and peer scope.
   - Require an exact `security_group_id`.
   - Require explicit `ethertype` and explicit `protocol`.
   - Require exactly one of `remote_ip_prefix`, `remote_group_id`, or `remote_address_group_id`.
   - For `direction=ingress`, treat `remote_ip_prefix` as the source CIDR or IP.
   - If the chosen protocol uses ports, require `multiport` rather than guessing a permissive port range.

4. Run a minimal security-group preflight.
   - Call `huaweicloud-vpc_ListSecurityGroups({ project_id, region, id: [security_group_id] })` first.
   - If no security group is returned, stop and report that the target group was not found in this scope.

5. Create exactly one ingress rule.
   - Call `huaweicloud-vpc_CreateSecurityGroupRule({ project_id, region, dry_run?, security_group_rule: { security_group_id, direction: "ingress", ethertype, protocol, multiport?, action?, priority?, enabled?, description?, remote_ip_prefix? or remote_group_id? or remote_address_group_id? } })`.
   - Use `dry_run` only when the user explicitly wants validation without mutation.

6. Confirm the result conservatively.
   - If the create result returns a rule ID, prefer `huaweicloud-vpc_ShowSecurityGroupRule({ project_id, region, security_group_rule_id })` for read-back confirmation.
   - If no read-back is performed, report request-stage acceptance only and say that the final effective state was not independently confirmed.

## Interpretation rules

- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.
- `ethertype` and `protocol` interact: `icmp` is for IPv4, `icmpv6` is for IPv6.
- `remote_ip_prefix`, `remote_group_id`, and `remote_address_group_id` are mutually exclusive peer selectors.
- Omitting all peer selectors would broaden the rule to all remotes, so this skill treats that as unsafe and requires exactly one peer selector.
- A successful create response can mean the request was accepted, not that traffic is already flowing end to end.

## Safety and scope

- This skill performs one mutating action.
- Create only one ingress rule in a single use of this skill.
- Do not create egress rules.
- Do not create, update, or delete the security group itself.
- Do not guess permissive defaults such as `0.0.0.0/0`, `::/0`, blank protocol meaning all protocols, or a missing peer selector.
- Do not silently guess a different `project_id` or `region`.

## Output checklist

1. region used
2. project used
3. target security group ID
4. exact ingress payload fields sent
5. whether `dry_run` was used
6. returned rule ID if present
7. whether read-back confirmation was performed
8. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
9. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
