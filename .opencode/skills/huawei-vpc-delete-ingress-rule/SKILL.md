---
name: huawei-vpc-delete-ingress-rule
description: Delete one known Huawei Cloud security group ingress rule by exact rule ID through the repo-local standalone helper in scripts/. Use only when the user explicitly wants that exact inbound rule removed and the current scope is already known or can be resolved safely. Executed by scripts/huawei_vpc_ingress_rule_delete.py.
compatibility: Prefers the repo-local standalone VPC helper script and wrapper commands in scripts/. If it is unavailable but Huawei Cloud VPC MCP tools or the repo-local VPC OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: delete-ingress-rule
---

# Huawei VPC Delete Ingress Rule

## What this skill does

- Delete exactly one security group ingress rule by explicit rule ID through `scripts/huawei_vpc_ingress_rule_delete.py`.
- Run a minimal preflight lookup (GET by rule ID) before deletion.
- Stop if the target rule is missing, is not an ingress rule, or fails an optional `security_group_id` guard.
- Perform one final visibility check and report whether the rule is still present.
- Restrict deletion to ingress rules by default; egress deletion requires explicit opt-in.

## Tool assumptions

Prefer the repo-local standalone helper path already used by the project VPC scripts.

Primary execution paths:

- `scripts/huawei_vpc_ingress_rule_delete.py`
- `scripts/delete-sg-ingress.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because the standalone helper defaults there. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

The scope file may also carry a `vpc_ingress_rule_delete` section for reusable rule IDs and guards; apply those only when the caller omitted the corresponding flag.

## Runtime fallback when required tools are unavailable

If the repo-local standalone VPC helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud VPC MCP tools or whether the repo-local VPC OpenAPI execution path is available, using:

- `scripts/huawei_vpc_ingress_rule_delete.py`
- `scripts/huawei_scope.py`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/run.py`
- `huaweicloud_services_server/mcp_server_vpc/src/mcp_server_vpc/config/vpc.json`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When the standalone helper is present and valid, prefer it. If it is unavailable but the active MCP tool surface or repo-local VPC OpenAPI execution chain can safely perform the same bounded workflow, that path is allowed instead. Only report a blocker when none of those paths can safely provide the required capability.

## Required inputs

Required directly or through scope defaults:

- `region`
- `project_id`
- `security_group_rule_id`

Optional inputs:

- `security_group_id` (as an additional exact guard)
- `allow_egress` (allow deleting egress rules too; default is ingress-only)
- `skip_preflight` (bypass the preflight existence/direction check)
- `skip_recheck` (bypass the final visibility recheck)
- `dry_run`

## Default workflow

1. Confirm explicit user intent and exact target scope.
   - This skill is destructive.
   - Use it only when the user has already explicitly asked to delete one exact ingress rule.
   - Once explicit user intent and exact rule ID are established, do not add an extra confirmation prompt inside this skill.

2. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope <path>`.
   - Apply `region` and `project_id` only when the caller omitted them. Do not silently mix a `project_id` from one region with a different `region`.

3. Run a minimal preflight lookup.
   - The helper GETs the rule by `--security-group-rule-id`.
   - If no rule is returned, stop and report that the target rule was not found in this scope.
   - If the returned rule direction is not `ingress` and `--allow-egress` was not supplied, stop and report that this skill deletes ingress rules only by default.
   - If `--security-group-id` was supplied as an extra guard and the returned rule belongs to a different group, stop and report the mismatch.

4. Delete exactly that one rule once.
   - Example:
     `python scripts/huawei_vpc_ingress_rule_delete.py delete --security-group-rule-id <rule_id>`
   - Use `--dry-run` to print the resolved target and preflight result without deleting.
   - Do not broaden deletion to other rules, even if they look similar.

5. Recheck visibility in the same scope.
   - The helper GETs the rule again after deletion.
   - If the result is empty (rule no longer found), report that the rule is no longer visible in this scope.
   - If the rule still appears, report that deletion is blocked or incomplete.
   - Use `--skip-recheck` only when the caller explicitly accepts not confirming the final state.

## Interpretation rules

- An empty preflight result means the target rule was not found in this region/project scope.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.
- A successful delete response does not by itself prove the rule is gone; the final visibility check confirms what is still visible.
- Exact rule-ID targeting is safer than property-based deletion by protocol, port, or CIDR.

## Safety and scope

- This skill is destructive.
- Delete only the explicitly identified ingress rule (or one rule when `--allow-egress` is explicitly supplied).
- Do not fuzzy-match by port, CIDR, description, or name-like hints.
- Do not silently guess a different `project_id` or `region`.
- Do not loop on retries; the helper performs one delete attempt and one final visibility check.

## Output checklist

1. scope file used
2. region used
3. project used
4. preflight rule match
5. whether the rule was confirmed as ingress (or `--allow-egress` was used)
6. whether optional `--security-group-id` guard matched
7. delete attempt result
8. final visibility check result
9. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
10. execution path used: `script`, `mcp-tools`, `repo-helper`, or `mixed`

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
