# Huawei skill starter skeleton

Use this as the default starting point for any new repo-local Huawei skill. Replace placeholders, then specialize by service and operation.

```md
---
name: huawei-<service>-<action>
description: <one-line purpose>
compatibility: Prefers Huawei Cloud <SERVICE> MCP tools in the current environment. If they are unavailable but the repo-local <SERVICE> helper path is present, this skill may use that bounded fallback path instead.
metadata:
  domain: huaweicloud
  service: <service>
  purpose: <purpose-slug>
---

# <Human-readable title>

## What this skill does

- <capability 1>
- <capability 2>

## Tool assumptions

Prefer the built-in Huawei Cloud MCP tools already exposed in this environment.

If `.opencode/huawei-scope.yaml` exists, read it first and extract `region`, `project_id`, and any other relevant defaults before proceeding. Apply any extracted value when the current call omitted that field.
Because `.opencode` is a hidden directory, do not rely only on glob results to decide this file is missing; prefer a direct read of the expected absolute path or a parent-directory lookup.

Primary tools:

- `<primary tool 1>`
- `<primary tool 2>`

Useful follow-up tools when narrowing scope:

- `<follow-up tool>`

@templates/runtime-fallback-section.template.md

## Required inputs

- <required input>

Optional inputs:

- `region` (if omitted, use the configured Huawei scope default when available)

## Default workflow

1. Confirm whether the action is read-only or mutating.
2. Read `.opencode/huawei-scope.yaml` first and apply safe defaults only where supported.
3. Validate exact required identifiers or creation fields.
4. Run a minimal preflight read when the operation is mutating or high-risk.
5. Execute exactly one bounded mutation or read path.
6. Re-read or summarize conservatively.

## Interpretation rules

- <rule>

## Safety and scope

- <safety rule>

## Output checklist

1. region used
2. project used
3. <operation-specific item>
4. <operation-specific item>
5. <overall outcome or blocker item>

Also include the shared item from:

@templates/output-checklist-execution-path.template.md
```

Notes:

- Replace `<PRIMARY_SERVICE>`, `<service>`, and `<AUX_SERVICES>` in the fallback template with concrete service names.
- Keep the fallback bounded to the current workflow; do not broaden it into unrelated runtime changes.
- Use the skeleton by default for new Huawei skills; do not ask for extra confirmation before applying it.
