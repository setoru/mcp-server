---
name: huawei-elb-create-loadbalancer
description: Create one or more Huawei Cloud ELB load balancers through the repo-local standalone ELB helper in this project. Use when the user explicitly wants batch ELB creation, dedicated ELBs, auto-created public IPs, traffic-billed bandwidth, random ELB names, or a scope-driven ELB create flow that should match scripts/huawei_elb_loadbalancer.py.
compatibility: Prefers the repo-local standalone ELB helper script and wrapper commands in scripts/. If they are unavailable but Huawei Cloud ELB MCP tools or the repo-local ELB OpenAPI execution path are exposed in the active runtime, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: elb
  purpose: create-loadbalancer
---

# Huawei ELB Create Load Balancer

## What this skill does

- Create one or more ELB load balancers through `scripts/huawei_elb_loadbalancer.py`.
- Support dedicated ELBs with `guaranteed=true`.
- Support creating and binding a public IP during ELB creation.
- Support traffic-billed public bandwidth, random ELB names, and batch creation through `--count`.
- Stop after the create requests return and report the accepted results conservatively.

## Tool assumptions

Prefer the repo-local standalone helper path already validated in this repository.

Primary execution paths:

- `scripts/huawei_elb_loadbalancer.py`
- `scripts/create-elb.cmd`
- `scripts/huawei_scope.py`

Read `.opencode/huawei-scope-2.yaml` first when it exists, because `scripts/huawei_scope.py` currently points there as the default scope file. If that file is absent, check `.opencode/huawei-scope.yaml` next, or pass `--scope-file` explicitly.

Apply scope defaults only when the current call omitted them. Because `.opencode` is a hidden directory, do not rely only on glob results to decide the scope file is missing; prefer a direct read of the expected path or an equivalent parent-directory lookup.

Do not print, rewrite, or commit secrets from the scope file. Use the scope file only to resolve runtime defaults such as `region`, `project_id`, and `elb_create`.

For billable or high-impact create behavior, prefer explicit flags even when matching scope defaults already exist:

- `--count`
- `--guaranteed`
- `--with-publicip`
- `--publicip-charge-mode`
- `--random-name`
- `--name-prefix`

## Runtime fallback when required tools are unavailable

If the repo-local standalone ELB helper path is unavailable or broken, do not stop immediately. First check whether the active runtime exposes Huawei Cloud ELB MCP tools or whether the repo-local ELB OpenAPI execution path is available, using:

- `scripts/huawei_elb_loadbalancer.py`
- `scripts/create-elb.cmd`
- `scripts/huawei_scope.py`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/run.py`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/config/config.yaml`
- `huaweicloud_services_server/mcp_server_elb/src/mcp_server_elb/config/elb.json`
- `assets/utils/server.py`
- `assets/utils/hwc_tools.py`
- `assets/utils/openapi.py`

When the standalone helper is present and valid, prefer it. If it is unavailable but the active MCP tool surface or repo-local ELB OpenAPI execution chain can safely perform the same bounded create workflow, that path is allowed instead. Only report a blocker when none of those paths can safely provide the required create capability.

## Required inputs

Required directly or through scope defaults:

- `region`
- `project_id`
- `loadbalancer.vip_subnet_cidr_id`
- `loadbalancer.availability_zone_list`

Required when creating dedicated ELBs:

- `loadbalancer.guaranteed=true`
- `loadbalancer.l4_flavor_id`

Required when creating a public IP during ELB creation:

- `loadbalancer.publicip.network_type`
- `loadbalancer.publicip.bandwidth.size`
- `loadbalancer.publicip.bandwidth.share_type`
- `loadbalancer.publicip.bandwidth.charge_mode`

Optional inputs:

- `count`
- `random_name`
- `name_prefix`
- `loadbalancer.name`
- `loadbalancer.description`
- `loadbalancer.vip_address`
- `loadbalancer.l7_flavor_id`
- `loadbalancer.charge_mode`
- `loadbalancer.admin_state_up`
- `loadbalancer.enterprise_project_id`
- `loadbalancer.protection_status`
- `loadbalancer.protection_reason`
- `loadbalancer.publicip.ip_version`
- `loadbalancer.publicip.description`
- `loadbalancer.publicip.bandwidth.name`

## Default workflow

1. Confirm explicit create intent and count.
   - This skill performs mutating, billable create actions.
   - Use it only when the user already explicitly wants new ELB instances created.

2. Resolve scope defaults.
   - Read `.opencode/huawei-scope-2.yaml` first.
   - If it is absent, check `.opencode/huawei-scope.yaml`.
   - If the desired defaults live somewhere else, pass `--scope-file <path>`.
   - Apply resolved `region`, `project_id`, and `elb_create` values only when the current request omitted them.

3. Validate bounded create inputs.
   - If `loadbalancer.vip_subnet_cidr_id` is still missing, stop and ask for it.
   - If `loadbalancer.availability_zone_list` is still missing, stop and ask for it.
   - If dedicated creation is requested, require `l4_flavor_id`.
   - If public IP creation is requested, require `network_type`, `bandwidth.size`, `bandwidth.share_type`, and `bandwidth.charge_mode`.
   - Do not silently switch between dedicated and shared ELB, or between traffic and bandwidth billing.

4. Prefer the repo-local create command once.
   - Scope-driven single create:
     `python scripts/huawei_elb_loadbalancer.py create`
   - Scope-driven batch create:
     `python scripts/huawei_elb_loadbalancer.py create --count <n>`
   - Dedicated public ELBs with traffic-billed bandwidth and random names:
     `python scripts/huawei_elb_loadbalancer.py create --count <n> --guaranteed --with-publicip --publicip-charge-mode traffic --random-name`
   - If the create flag name needs to match the API field, remember that CLI `--vip-subnet-id` maps to payload field `vip_subnet_cidr_id`.

5. Stop after the create result.
   - Treat the returned response as request acceptance, not as proof that the ELB is already fully provisioned.
   - When `--count > 1`, expect one ordered response entry per submitted create request.

## Interpretation rules

- ELB creation is asynchronous; a successful response means the request was accepted, not that the ELB is already `ACTIVE`.
- When `--count > 1` or `--random-name` is enabled, the helper generates unique ELB names automatically.
- When a generated ELB name is used together with `publicip.bandwidth` and no bandwidth name is supplied, the helper derives a bandwidth name from the ELB name.
- `project_id` is region-scoped in Huawei Cloud, so do not silently mix a project from one region with another region.

## Safety and scope

- This skill performs only ELB create requests.
- Do not auto-create listeners, pools, members, health checks, or security policies after creation.
- Do not guess subnet IDs, availability zones, flavor IDs, or public IP billing settings.
- Do not exceed the explicitly requested `count`.
- Do not modify or commit the scope file unless the user explicitly asked for that change.

## Output checklist

1. scope file used
2. region used
3. project used
4. count requested and count submitted
5. whether dedicated ELB, public IP, traffic billing, and random naming were enabled
6. essential create payload fields actually sent
7. returned ELB names, IDs, and visible public IP fields when present
8. exact blocker if creation could not proceed
9. overall outcome at request stage: `completed`, `partially completed`, or `blocked`
10. execution path used: `script`, `mcp-tools`, `repo-helper`, `mixed`, or `not-run`
