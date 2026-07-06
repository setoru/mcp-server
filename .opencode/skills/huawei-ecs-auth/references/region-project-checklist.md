# Huawei ECS region and project checklist

Use this checklist before concluding that Huawei Cloud credentials are invalid.

## Verification order

1. Confirm which region is being tested.
2. List accessible IAM projects for that region.
3. Pick the target `project_id`.
4. Run a read-only ECS list call.
5. If a server is returned, optionally run `ShowServer`.

## Recommended tool sequence

### A. Discover project access

```text
huaweicloud-iam_KeystoneListAuthProjects({ region })
```

Use this first when the user did not provide a `project_id`.

### B. Primary ECS check

```text
huaweicloud-ecs_ListServersDetails({ project_id, region, limit: 10 })
```

Why this is preferred:

- read-only
- sufficient to verify credentials + project scope + ECS read access
- empty result still proves the call succeeded

### C. Stronger follow-up confirmation

```text
huaweicloud-ecs_ShowServer({ project_id, region, server_id })
```

Only run this when the list call already returned a concrete server ID.

## Default assumptions

- If region is omitted, `cn-north-4` is a practical first region to test, but it should be presented as an explicit assumption rather than a guaranteed default.
- If multiple projects are visible and the user did not specify one, a lightweight validation may use the first project, but that assumption must be stated.

## Do not do these

- Do not ask the user for `X-Auth-Token` for this workflow.
- Do not use mutating ECS calls for credential verification.
- Do not conclude “invalid credentials” before checking whether the problem is only region/project selection.
