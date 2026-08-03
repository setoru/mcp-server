---
name: huawei-vpc-delete-ingress-rule
description: Remove one known Huawei Cloud security group ingress rule by exact rule ID. Note that the repo-local standalone script set under scripts/ does not currently ship a dedicated delete helper; this skill identifies the target rule with the list-rules helper and then calls the Huawei Cloud VPC API delete path directly (or an equivalent MCP tool when present).
compatibility: Prefers the repo-local standalone VPC helper scripts in scripts/ for discovery. Deletion itself is not covered by a standalone helper in this repo, so it falls back to the active Huawei Cloud VPC MCP tool or the repo-local VPC OpenAPI execution path.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: delete-ingress-rule
---

# Huawei VPC Delete Ingress Rule

## What this skill does

- Delete exactly one security group ingress rule by explicit rule ID.
- Use the repo-local list-rules helper to confirm the target rule exists, is an ingress rule, and (optionally) belongs to an expected security group.
- Perform deletion through an available supported path (Huawei Cloud VPC MCP tool or repo-local VPC OpenAPI execution chain), because `scripts/` does not currently ship a standalone delete helper.
- Re-read the rule afterwards to confirm it is no longer visible.

## Tool assumptions

For target discovery, prefer the repo-local standalone helper:

- `scripts/huawei_vpc_security_group_rules.py` (list / show)
- `scripts/show-sg-rule.cmd`
- `scripts/huawei_scope.py`

For deletion itself, no standalone `scripts/huawei_vpc_*` delete helper exists in this repo. Use one of:

- `huaweicloud-vpc_DeleteSecurityGroupRule` (Huawei Cloud VPC MCP tool)
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/run.py`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/config/vpc.json`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists; if it is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope` explicitly. Apply `region` and `project_id` only when the caller omitted them. Do not silently mix a `project_id` from one region with a different `region`.

If no deletion path is available at all, report a blocker instead of guessing.

## Required inputs

Required directly or through scope defaults:

- `region`
- `project_id`
- `security_group_rule_id`

Optional inputs:

- `security_group_id` (as an additional exact guard)

## Default workflow

1. Confirm explicit user intent and exact target scope.
   - This skill is destructive.
   - Use it only when the user has already explicitly asked to delete one exact ingress rule.

2. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope <path>`.
   - Apply `region` and `project_id` only when the caller omitted them.

3. Run a minimal preflight lookup with the list-rules helper.
   - `python scripts/huawei_vpc_security_group_rules.py show --security-group-rule-id <rule_id> --json-output`
   - If no rule is returned, stop and report that the target rule was not found in this scope.
   - If the returned rule direction is not `ingress`, stop and report that this skill only deletes ingress rules.
   - If `--security-group-id` was supplied as an extra guard and the returned rule belongs to a different group, stop and report the mismatch.

4. Delete exactly that one rule once.
   - Use the available supported deletion path (VPC MCP tool or repo-local VPC OpenAPI chain).
   - Do not broaden deletion to other rules, even if they look similar.

5. Recheck visibility in the same scope.
   - `python scripts/huawei_vpc_security_group_rules.py show --security-group-rule-id <rule_id>`
   - If the result is empty (rule no longer found), report that the rule is no longer visible in this scope.
   - If the rule still appears, report that deletion is blocked or incomplete.

## Interpretation rules

- An empty preflight result means the target rule was not found in this region/project scope.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.
- A successful delete response does not by itself prove the rule is gone; use the final visibility check to confirm what is still visible.
- Exact rule-ID targeting is safer than property-based deletion by protocol, port, or CIDR.

## Safety and scope

- This skill is destructive.
- Delete only the explicitly identified ingress rule.
- Do not delete egress rules, multiple rules, or the security group itself.
- Do not fuzzy-match by port, CIDR, description, or name-like hints.
- Do not silently guess a different `project_id` or `region`.
- Do not loop on retries; perform one delete attempt and one final visibility check.

## Output checklist

1. scope file used
2. region used
3. project used
4. preflight rule match (via list-rules helper)
5. whether the rule was confirmed as ingress
6. whether optional `security_group_id` guard matched
7. deletion path used (`mcp-tools`, `repo-helper`, or `mixed`)
8. delete attempt result
9. final visibility check result
10. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
