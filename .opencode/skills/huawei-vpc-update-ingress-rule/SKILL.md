---
name: huawei-vpc-update-ingress-rule
description: Modify one Huawei Cloud VPC security group ingress rule through the repo-local standalone helper in scripts/. Use when the user explicitly wants to change an existing inbound rule (action, priority, port scope, peer, enabled state, description) and already knows the exact rule ID. Executed by scripts/huawei_vpc_ingress_rule_update.py.
compatibility: Prefers the repo-local standalone VPC helper script and wrapper commands in scripts/. If it is unavailable but Huawei Cloud VPC MCP tools or the repo-local VPC OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: update-ingress-rule
---

# Huawei VPC Update Ingress Rule

## What this skill does

- Modify exactly one security group ingress rule through `scripts/huawei_vpc_ingress_rule_update.py` (PUT replace).
- Pin the rule direction to `ingress` and refuse to modify egress rules.
- Fetch the existing rule first, overlay only the caller-supplied fields, and preserve untouched fields in the PUT body.
- Strip system-only fields (`id`, `created_at`, `updated_at`, `tenant_id`, `project_id`) so the PUT body stays valid.

## Tool assumptions

Prefer the repo-local standalone helper path already used by the project VPC scripts.

Primary execution paths:

- `scripts/huawei_vpc_ingress_rule_update.py`
- `scripts/update-sg-ingress.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because the standalone helper defaults there. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

The scope file may also carry a `vpc_ingress_rule_update` section for reusable override defaults; apply those only when the caller omitted the corresponding flag.

## Runtime fallback when required tools are unavailable

If the repo-local standalone VPC helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud VPC MCP tools or whether the repo-local VPC OpenAPI execution path is available, using:

- `scripts/huawei_vpc_ingress_rule_update.py`
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
- `security_group_rule_id` (the exact ingress rule to modify)

Optional inputs (any subset may be supplied; omitted fields keep their existing values):

- `security_group_id` (override the parent group carried in the PUT body)
- `ethertype` (`IPv4` or `IPv6`)
- `protocol` (`tcp`/`udp`/`icmp`/`icmpv6`/`any`)
- `multiport` (required for `tcp`/`udp` if the existing rule has none)
- `action` (`allow` or `deny`)
- `priority` (0..100)
- `enabled` (true/false)
- `description`
- `remote_ip_prefix`
- `remote_group_id`
- `remote_address_group_id`
- `dry_run`

## Default workflow

1. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope <path>`.
   - Apply `region` and `project_id` only when the caller omitted them. Do not silently mix a `project_id` from one region with a different `region`.

2. Fetch the existing rule first.
   - The helper GETs the rule by `--security-group-rule-id` before building the PUT body.
   - If the existing rule's `direction` is not `ingress`, the helper stops; this skill only modifies ingress rules.

3. Choose which fields to change.
   - Pass only the flags the caller actually wants to change; the helper preserves every other field from the existing rule.
   - At most one of `--remote-ip-prefix`, `--remote-group-id`, `--remote-address-group-id`. Omitting all three keeps the existing peer selector.

4. Run the update command.
   - Example (change action and priority only):
     `python scripts/huawei_vpc_ingress_rule_update.py update --security-group-rule-id <rule_id> --action deny --priority 5`
   - Example (switch peer to a remote group):
     `python scripts/huawei_vpc_ingress_rule_update.py update --security-group-rule-id <rule_id> --remote-group-id <sg_id>`
   - Use `--dry-run` to print the resolved PUT body without sending it.

5. Confirm the result.
   - The helper prints the resolved PUT body and the API response.
   - Report the updated field values, not just "updated".

## Interpretation rules

- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a `project_id` from one region with a different `region`.
- The PUT replaces the whole rule; the helper overlays flags onto the existing rule so untouched fields survive, and strips system-only fields that the API rejects on write.
- `ethertype` and `protocol` interact: `icmp` is for IPv4, `icmpv6` is for IPv6.
- `remote_ip_prefix`, `remote_group_id`, and `remote_address_group_id` are mutually exclusive peer selectors.
- A successful update response means the request was accepted; re-read the rule if the caller needs independent confirmation of the new effective state.

## Safety and scope

- This skill performs one mutating action.
- Modify only one ingress rule in a single use of this skill.
- Do not modify egress rules.
- Do not create, delete, or modify the security group itself.
- Do not fuzzy-match a rule by port, CIDR, or description; require the exact `--security-group-rule-id`.
- Do not silently guess a different `project_id` or `region`.

## Output checklist

1. scope file used
2. region used
3. project used
4. target rule ID
5. existing direction confirmed as `ingress`
6. fields changed
7. resolved PUT body
8. whether `--dry-run` was used
9. API response summary
10. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
11. execution path used: `script`, `mcp-tools`, `repo-helper`, or `mixed`
