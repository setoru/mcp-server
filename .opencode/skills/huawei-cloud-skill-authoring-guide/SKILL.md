---
name: huawei-cloud-skill-authoring-guide
description: Authoring guide for adding new Huawei Cloud repo-local skills in this repository. Use when creating a new Huawei service skill so it matches the repo's naming, scope-default, safety, and output conventions.
compatibility: Applies to repo-local Huawei Cloud skills under .opencode/skills and the shared scope-default runtime in assets/utils/hwc_tools.py.
metadata:
  domain: huaweicloud
  service: shared
  purpose: skill-authoring-guide
---

# Huawei Cloud Skill Authoring Guide

## What this skill does

- Defines the standard conventions for creating new Huawei Cloud skills in this repository.
- Explains how to align a new skill with the existing runtime, naming, scope-default injection, and safety model.
- Provides a repeatable checklist so new Huawei skills behave consistently across ECS, NAT, CCE, VPC, and future services.

## When to use this guide

Use this guide whenever you add or refactor a repo-local Huawei Cloud skill under `.opencode/skills/`.

Typical triggers:

- A new Huawei Cloud service is exposed through MCP tools and needs a skill.
- An existing Huawei skill needs to be split, merged, or standardized.
- A new skill must participate in `.opencode/huawei-scope.yaml` default argument injection.

Default reusable assets for new Huawei skills in this guide directory:

- `@templates/runtime-fallback-section.template.md`
- `@templates/output-checklist-execution-path.template.md`
- `@templates/new-huawei-skill.skeleton.md`

## Naming and file layout conventions

1. Create one directory per skill:
   - `.opencode/skills/<skill-slug>/SKILL.md`

2. Use a Huawei-prefixed slug:
   - `huawei-<service>-<action>`
   - Examples:
     - `huawei-ecs-list-servers`
     - `huawei-nat-delete-gateway-with-snat-cleanup`
     - `huawei-cce-create-cluster`

3. Keep the `name:` in frontmatter exactly equal to the directory slug.

4. Use `metadata` consistently:
   - `domain: huaweicloud`
   - `service: <service>` such as `ecs`, `nat`, `cce`, `vpc`, or `shared`
   - `purpose: <short-purpose-slug>`

5. For new Huawei skills, default to the shared template assets above.
   - Do not ask for extra confirmation before applying them.
   - Start from `@templates/new-huawei-skill.skeleton.md` unless there is a clear repo-local reason not to.

## Required document structure

Every Huawei skill should follow this section order unless there is a strong reason not to:

1. Frontmatter
2. `# <Human-readable title>`
3. `## What this skill does`
4. `## Tool assumptions`
5. `## Runtime fallback when required tools are unavailable`
6. `## Required inputs`
7. `## Default workflow`
8. `## Interpretation rules`
9. `## Safety and scope`
10. `## Output checklist`

Do not skip the safety or output sections, even for read-only skills.

## Tool assumption conventions

1. Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

2. Name the actual primary tools explicitly.
   - Good:
     - `huaweicloud-ecs_CreateServers`
     - `huaweicloud-nat_DeleteNatGateway`
     - `huaweicloud-cce_ListClusters`

3. If a skill depends on auxiliary services such as IAM, VPC, or EIP, list them as useful follow-up tools.

4. Mention scope behavior explicitly.
   - State that `.opencode/huawei-scope.yaml` or the user scope file may inject defaults when the current call omits them.
   - State that `.opencode` is a hidden directory, so agents must not rely only on glob results to decide the project scope file is missing; prefer direct read of the expected absolute path or a parent-directory lookup equivalent to `assets/utils/hwc_tools.py::_find_project_scope_path()`.
   - Distinguish two `name` cases clearly:
     - top-level `name` in the scope file is an AI-side fuzzy hint only and must not be injected directly
     - segment-local `name` values may be injected only when they are already intended as exact API-safe defaults for that mapped tool family

## Runtime-fallback conventions

Every Huawei skill should include a dedicated `## Runtime fallback when required tools are unavailable` section.

By default, author that section by copying and filling in `@templates/runtime-fallback-section.template.md`.

That section should say all of the following:

1. If the expected Huawei MCP tools are not exposed in the active runtime, do not stop immediately.
2. Check the matching repo-local service execution path first.
3. Reuse the repo's shared OpenAPI execution chain through:
   - `assets/utils/server.py`
   - `assets/utils/hwc_tools.py`
   - `assets/utils/openapi.py`
4. If the full service path is invalid or unavailable but a matching `*_lite` service exposes the same operation safely, that `*_lite` path is allowed.
5. Keep the fallback bounded to the current skill's intended workflow only.
6. Declare a blocker only when neither the active MCP tool surface nor the repo-local fallback path can safely perform the required operation.

When relevant, the section should also list the exact repo-local service files to check, such as:

- `huaweicloud_services_server/mcp_server_<service>/src/mcp_server_<service>/run.py`
- `huaweicloud_services_server/mcp_server_<service>/src/mcp_server_<service>/config/config.yaml`
- `huaweicloud_services_server/mcp_server_<service>/src/mcp_server_<service>/config/<service>.json`

If the skill depends on an auxiliary service such as IAM, EPS, VPC, or EIP to resolve missing inputs, document that dependency explicitly in the fallback section too. Either name the auxiliary repo-local helper path that is allowed, or say clearly that the skill blocks when the auxiliary helper path is unavailable.

## Scope-default conventions

This repository now supports two layers of Huawei defaults:

1. **Top-level shared defaults** in `.opencode/huawei-scope.yaml`
   - `region`
   - `project_id`
   - `enterprise_project_id`
   - `vpc_id`
   - `subnet_id`

2. **Tool-family segmented defaults** in `.opencode/huawei-scope.yaml`
   - Examples already in use:
     - `ecs_list`, `ecs_create`, `ecs_delete`, `ecs_stop`
     - `nat_list`, `nat_create_gateway`, `nat_create_snat`, `nat_delete`
     - `cce_list`, `cce_create`, `cce_hibernate`, `cce_awake`

### How segmented defaults work

- Explicit tool args win first.
- Matching segmented defaults are merged next.
- Top-level shared defaults are applied after that for supported missing fields.
- `project_id` may still be discovered from IAM when missing and resolvable from region + credentials.

### Scope source precedence

When documenting or debugging Huawei defaults, describe the source order accurately:

1. explicit tool args
2. project-local `.opencode/huawei-scope.yaml`
3. user scope file
4. built-in config defaults and environment-backed fallbacks

Inside the already merged scope object, segmented defaults override top-level defaults only for the matching mapped tools.

### When adding a new Huawei skill

If the new skill has stable defaultable inputs, also update:

- `.opencode/huawei-scope.yaml`
- `assets/utils/hwc_tools.py`
- `tests/test_huawei_scope_defaults.py`

Specifically:

1. Add a new segmented section name to `_normalize_scope_config()`.
2. Add it to `_extract_tool_scope_defaults()`.
3. Map the relevant MCP tool names in `_resolve_tool_scope_defaults()`.
4. Add at least one regression test proving the segment is injected correctly.

## Required-input conventions

1. Required inputs must reflect the real mutation/query boundary.
   - Read-only list skills may allow `project_id` discovery from region.
   - Mutating skills should require exact identifiers unless IAM/project discovery is a safe first step.

2. Do not claim fuzzy names are acceptable for destructive actions.
   - For delete, hibernate, awake, shutdown, or similar operations, require exact IDs.

3. If a service has nested request bodies, document the nested required fields explicitly.
   - Example: `server.imageRef`, `metadata.name`, `spec.hostNetwork.vpc`

4. When a field is only conditionally required, say so clearly.
   - Example: ENI-only fields for CCE create.

## Default workflow conventions

Every Huawei skill workflow should usually follow this shape:

1. Confirm whether the action is read-only or mutating.
2. Read `.opencode/huawei-scope.yaml` first.
   - Prefer a direct read of the expected project-local path instead of hidden-directory globbing alone. If the direct path is uncertain, walk parent directories and look for `.opencode/huawei-scope.yaml` the same way the runtime helper does.
   - If the file exists, extract `region`, `project_id`, `enterprise_project_id`, and any other relevant defaults.
   - Apply any extracted value when the caller omitted that field.
   - If `region` is still missing after reading scope defaults, stop and ask for the target region.
   - If `project_id` is still missing, discover it from `huaweicloud-iam_KeystoneListAuthProjects({ region })`.
3. Validate exact required identifiers or creation fields.
4. Run a minimal preflight read when the operation is mutating or high-risk.
5. Execute exactly one bounded mutation path.
6. Re-read or summarize conservatively.

### For read-only skills

- Prefer a narrow list call.
- Use a detail/read call only when one resource is clearly targeted or the user explicitly asked for detail.

### For mutating skills

- Require explicit user intent before execution.
- Use exact IDs for destructive actions.
- Treat async acceptance as acceptance, not terminal success.
- If follow-up reads are skipped, say so explicitly.

### For multi-step mutating skills

- Keep the cleanup/secondary mutation path bounded.
- Do not loop indefinitely.
- Do not broaden cleanup automatically to unrelated resources.
- If partial success is possible, define how to report it.

### For composite cross-service skills

If a skill spans multiple Huawei services, such as CCE + ECS or NAT + EIP:

- name all primary tools across services explicitly
- define the exact step order
- bound each secondary mutation to the resources returned by the current run
- state what happens when the first mutation succeeds but a later one fails
- make the partial-outcome reporting contract explicit

## Interpretation-rule conventions

Interpretation rules should explain:

1. Async semantics
   - A successful response often means “request accepted,” not “resource fully ready/deleted/stopped.”

2. Region/project scoping
   - `project_id` is region-scoped in Huawei Cloud; do not silently mix a project from one region with another region.

3. Important API-specific caveats
   - Example: `detail=true` expands list payloads.
   - Example: `SOFT` vs `HARD` stop semantics.
   - Example: EIP reuse must not guess among multiple candidates.

## Safety and scope conventions

Every Huawei skill must state what it will **not** do.

Minimum rules:

- Do not infer a different `project_id` or `region` silently.
- Do not fuzzy-match destructive targets.
- Do not claim terminal success without a confirming read.
- Do not chain unrelated mutations.
- Do not echo sensitive values such as `ak`, `sk`, passwords, or equivalent credentials in examples, payload summaries, or output checklists.

For destructive skills, explicitly say:

- what exact resources may be deleted or changed
- what dependent resources must **not** be deleted automatically
- whether retries are allowed, and if so, how many

For create skills, explicitly say:

- whether follow-up resources may be created automatically
- whether billable options may be guessed (usually **no**)
- how partially created resources are reported

For list/auth-diagnosis skills, explicitly say:

- whether a fallback region probe is allowed
- if allowed, that it is a special diagnostic exception rather than the general convention

## Output checklist conventions

Every Huawei skill should end with a checklist tailored to the operation.

Minimum checklist fields for most skills:

1. `region used`
2. `project used`
3. `execution path used` such as `mcp-tools`, `repo-helper`, `mixed`, or `not-run`
4. target identifiers or create payload fields actually sent
5. acceptance / blocker / confirmation status
6. `overall outcome` when the skill is mutating or multi-step

By default, add the execution-path item by reusing `@templates/output-checklist-execution-path.template.md`.

For mutating skills, prefer wording like:

- `overall outcome at request stage: completed / partially completed / blocked`

Use “request stage” when the underlying API is asynchronous.

## How to decide whether a new segmented scope section is needed

Add a new section in `.opencode/huawei-scope.yaml` when all of these are true:

1. The skill is likely to be reused repeatedly.
2. The skill has stable, repeatable defaults.
3. The defaults materially reduce repeated operator input.
4. Injecting them is safe when explicit args are absent.

Do **not** add segmented scope defaults when:

- the action is too one-off or highly variable
- the defaults would be dangerous if reused implicitly
- the operation routinely requires fresh IDs or one-time billable choices

## Recommended authoring checklist

Before finalizing a new Huawei skill:

1. Confirm the skill name and directory slug match.
2. Confirm the section order matches the repo convention.
3. Confirm the draft started from `@templates/new-huawei-skill.skeleton.md` or an intentionally equivalent structure.
4. Confirm the `## Default workflow` step 1 classifies the action as read-only or mutating.
5. Confirm the `## Default workflow` step 2 reads `.opencode/huawei-scope.yaml` explicitly and extracts `region`, `project_id`, and `enterprise_project_id` as defaults.
6. Confirm it also says not to rely only on glob over hidden `.opencode` paths and instead to prefer direct-read or parent-walk lookup.
7. Confirm scope-default wording matches the current runtime.
8. Confirm the dedicated runtime-fallback section came from `@templates/runtime-fallback-section.template.md` and was filled with concrete service paths.
9. Confirm the output checklist reused `@templates/output-checklist-execution-path.template.md`.
10. Confirm the output checklist allows `not-run` when the skill blocks before any execution path is used.
11. Confirm required inputs match the actual MCP tool surface.
12. Confirm destructive skills forbid fuzzy matching.
13. Confirm async operations are described as acceptance, not completion.
14. If adding segmented defaults, update runtime mapping and tests.
15. Re-read the skill and compare tone/style against existing Huawei skills.

## Region-default convention for new skills

For new Huawei skills, the mandatory convention is:

1. Read `.opencode/huawei-scope.yaml` first and extract `region` as a default.
2. Do not treat a hidden-directory glob miss as proof that the file does not exist; prefer reading the direct absolute path or walking parent directories until `.opencode/huawei-scope.yaml` is found.
3. Use the explicit `region` if provided by the caller — it overrides scope defaults.
4. Otherwise apply the scope-extracted `region`.
5. If `region` is still missing after reading scope defaults, stop and ask for the target region.

Do not introduce silent `cn-north-4` fallback logic in any skill.
Do not assume any default region when the scope file is absent or does not define `region`.
If a diagnostic/auth-check skill intentionally probes a known region as an initial check, document that as an explicit special case with a clear user-visible note.

## Output checklist

When using this guide to author a new Huawei skill, produce:

1. proposed skill name and directory slug
2. target Huawei service and primary MCP tools
3. read-only vs mutating classification
4. required inputs
5. optional inputs
6. whether a new segmented scope section is needed
7. runtime mapping changes required, if any
8. tests required, if any
9. notable safety constraints
