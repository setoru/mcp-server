---
name: huawei-vpc-delete-ingress-rule
description: Delete one known Huawei Cloud security group ingress rule by exact rule ID through Huawei Cloud VPC MCP tools. Use only when the user explicitly wants that exact inbound rule removed and the current scope is already known or can be resolved safely.
compatibility: Prefers Huawei Cloud VPC MCP tools in the current environment. If they are unavailable but the repo-local VPC helper path is present, this skill may use that bounded fallback path instead. IAM MCP tools remain useful follow-ups for project discovery.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: delete-ingress-rule
---

# Huawei VPC Delete Ingress Rule

## What this skill does

- Delete exactly one security group ingress rule by explicit rule ID.
- Run a minimal preflight lookup before deletion.
- Stop if the target rule is missing or is not an ingress rule.
- Perform one final visibility check and report the result conservatively.

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and `enterprise_project_id` as defaults before proceeding. Apply any extracted value when the tool supports it and the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.
The same scope file may also contain `name`, but that field is an AI-side fuzzy-match hint and must not be passed directly as an API filter unless it has already been normalized to an exact resource name.

Primary tools:

- `huaweicloud-vpc_ListSecurityGroupRules`
- `huaweicloud-vpc_DeleteSecurityGroupRule`

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
- `security_group_rule_id`

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)
- `security_group_id` (as an additional exact guard)

## Default workflow

1. Confirm explicit user intent and exact target scope.
   - This skill is destructive.
   - Use it only when the user has already explicitly asked to delete one exact ingress rule.
   - Once explicit user intent and exact rule ID are established, do not add an extra confirmation prompt inside this skill.

2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone.
   - If the file exists, extract `region`, `project_id`, and `enterprise_project_id` as defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is missing, prefer discovering it with `huaweicloud-iam_KeystoneListAuthProjects({ region })` before continuing.
   - Do not silently mix a `project_id` from one region with a different `region`.

3. Run a minimal preflight lookup.
   - Call `huaweicloud-vpc_ListSecurityGroupRules({ project_id, region, id: [security_group_rule_id] })` first.
   - If no rule is returned, stop and report that the target rule was not found in this scope.
   - If the returned rule direction is not `ingress`, stop and report that this skill only deletes ingress rules.
   - If `security_group_id` was supplied as an extra guard and the returned rule belongs to a different group, stop and report that mismatch.

4. Delete exactly that one rule once.
   - Call `huaweicloud-vpc_DeleteSecurityGroupRule({ project_id, region, security_group_rule_id })`.
   - Do not broaden deletion to other rules, even if they look similar.

5. Recheck visibility in the same scope.
   - Call `huaweicloud-vpc_ListSecurityGroupRules({ project_id, region, id: [security_group_rule_id] })`.
   - If the result is empty, report that the rule is no longer visible in this scope.
   - If the rule still appears, report that deletion is blocked or incomplete.

## Interpretation rules

- An empty preflight list means the target rule was not found in this region/project scope.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.
- A successful delete response does not by itself prove the rule is gone; use the final visibility check to confirm what is still visible in this scope.
- This skill treats exact rule-ID targeting as safer than property-based deletion by protocol, port, or CIDR.

## Safety and scope

- This skill is destructive.
- Delete only the explicitly identified ingress rule.
- Do not delete egress rules, multiple rules, or the security group itself.
- Do not fuzzy-match by port, CIDR, description, or name-like hints.
- Do not silently guess a different `project_id` or `region`.
- Do not loop on retries; perform one delete attempt and one final visibility check.

## Output checklist

1. region used
2. project used
3. preflight rule match
4. whether the rule was confirmed as ingress
5. whether optional `security_group_id` guard matched
6. delete attempt result
7. final visibility check result
8. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
9. execution path used: `mcp-tools`, `repo-helper`, or `mixed`
