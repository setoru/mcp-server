# Huawei ECS auth failure guide

Use this guide to classify failures when validating Huawei Cloud ECS access through MCP tools.

## 1. Missing credentials

Typical signal:

- tool error similar to `MISSING_CREDENTIALS`
- message similar to `HUAWEI_ACCESS_KEY or HUAWEI_SECRET_KEY not configured`

Interpretation:

- The MCP server does not currently have usable Huawei AK/SK configured.

Report:

- Explain that this repo expects `HUAWEI_ACCESS_KEY` and `HUAWEI_SECRET_KEY`, or equivalent `ak` / `sk` values in the server config path.
- Do not claim credentials are invalid; they may simply be absent.

## 2. Invalid credentials or signing failure

Typical signal:

- auth/signature failure
- unauthorized style API response
- IAM and ECS calls both fail before returning readable project/resource data

Interpretation:

- The configured AK/SK is present but not accepted.

Report:

- Say the credentials appear configured but unusable.
- Recommend verifying the AK/SK pair and whether it belongs to the intended Huawei Cloud account.

## 3. Region or project mismatch

Typical signal:

- IAM project listing succeeds in one region but ECS query fails in another
- project list does not include the requested project
- ECS responds as though the project or scope is not found

Interpretation:

- Credentials may be valid, but the chosen region or `project_id` is wrong for this check.

Report:

- State that auth may still be valid.
- Separate the scope problem from the credential problem.

## 4. Permission denied

Typical signal:

- IAM project listing works
- ECS read call returns permission denied / forbidden

Interpretation:

- Credentials are valid enough to authenticate, but the identity lacks ECS read permissions in that scope.

Report:

- Say authentication works, but ECS read permission is insufficient.
- Do not describe it as a credential failure.

## 5. Empty but valid result

Typical signal:

- ECS list call succeeds
- result contains zero servers

Interpretation:

- Credential verification succeeded for read access.
- There are simply no ECS resources in that region/project scope.

Report:

- Explicitly say the credentials are usable.
- Explicitly say no ECS instances were found.
