---
name: huawei-vpc-add-ingress-rule
description: Create one Huawei Cloud VPC security group ingress rule through the repo-local standalone helper in scripts/. Use when the user explicitly wants inbound access added and already knows the exact target security group, protocol, port scope, and remote peer. Executed by scripts/huawei_vpc_ingress_rule.py.
compatibility: Prefers the repo-local standalone VPC helper script and wrapper commands in scripts/. If it is unavailable but Huawei Cloud VPC MCP tools or the repo-local VPC OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: vpc
  purpose: add-ingress-rule
---

# Huawei VPC Add Ingress Rule

## What this skill does

- Create exactly one security group ingress rule through `scripts/huawei_vpc_ingress_rule.py`.
- Fix the rule direction to inbound access only (`direction=ingress`).
- Run a minimal preflight lookup on the target security group before creation (skippable only with explicit intent).
- Read back the created rule when a rule ID is returned, and report the result conservatively.

## Tool assumptions

Prefer the repo-local standalone helper path already used by the project VPC scripts.

Primary execution paths:

- `scripts/huawei_vpc_ingress_rule.py`
- `scripts/add-sg-ingress.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because the standalone helper defaults there. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

The scope file may also carry a `vpc_ingress_rule_create` section for reusable rule defaults; apply those only when the caller omitted the corresponding flag.

## Runtime fallback when required tools are unavailable

If the repo-local standalone VPC helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud VPC MCP tools or whether the repo-local VPC OpenAPI execution path is available, using:

- `scripts/huawei_vpc_ingress_rule.py`
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
- `security_group_id`
- `ethertype` (defaults to `IPv4` if neither flag nor scope value is provided)
- `protocol` (defaults to `tcp` if neither flag nor scope value is provided)
- exactly one of `remote_ip_prefix`, `remote_group_id`, or `remote_address_group_id`

Conditionally required inputs:

- `multiport` when the chosen protocol uses ports, such as `tcp` or `udp`

Optional inputs:

- `description`
- `action` (defaults to `allow`); only `allow` or `deny`
- `priority` (0..100)
- `enabled` (defaults to `true`)
- `skip_preflight` (bypass the target security-group existence check)
- `dry_run`

## Default workflow

1. Treat this as the inbound access rule skill.
   - This skill creates ingress only. The helper pins `direction` to `ingress`.

2. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope <path>`.
   - Apply `region` and `project_id` only when the caller omitted them. Do not silently mix a `project_id` from one region with a different `region`.

3. Require explicit target and peer scope.
   - Require an exact `--security-group-id`.
   - Require explicit `--ethertype` and explicit `--protocol` (or scope-section defaults).
   - Require exactly one of `--remote-ip-prefix`, `--remote-group-id`, or `--remote-address-group-id`.
   - For `direction=ingress`, treat `--remote-ip-prefix` as the source CIDR or IP.
   - If the chosen protocol uses ports, require `--multiport` rather than guessing a permissive port range.

4. Run a minimal security-group preflight.
   - The helper lists the security group by ID before creating the rule.
   - If no security group is returned, stop and report that the target group was not found in this scope (or use `--skip-preflight` only when the caller explicitly accepts the risk).

5. Create exactly one ingress rule.
   - Example:
     `python scripts/huawei_vpc_ingress_rule.py create --security-group-id <sg_id> --protocol tcp --multiport 8080 --remote-ip-prefix 10.0.0.0/24`
   - Use `--dry-run` only when the user explicitly wants validation without mutation.
   - Use `--action deny` explicitly if the intent is a deny rule; otherwise `allow` applies by default.

6. Confirm the result conservatively.
   - If the create result returns a rule ID, the helper read back the rule for confirmation.
   - If the read-back was not performed or failed, report request-stage acceptance only and say that the final effective state was not independently confirmed.

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

1. scope file used
2. region used
3. project used
4. target security group ID
5. exact ingress payload fields sent
6. whether `--dry-run` was used
7. whether preflight was run (or explicitly skipped)
8. returned rule ID if present
9. whether read-back confirmation was performed
10. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
11. execution path used: `script`, `mcp-tools`, `repo-helper`, or `mixed`
