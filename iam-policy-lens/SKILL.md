---
name: iam-policy-lens
description: Polyglot Cloud Access Scanner (Python, Go, & TypeScript) to statically identify Google Cloud (GAPIC) client library invocations, map them to required IAM permissions, and generate consolidated GCP IAM V3 Allow Policies.
---

# IAM Policy Lens Instructions

Use this skill when you need to audit, analyze, or map Google Cloud API (GAPIC) usage in Python, Go, or TypeScript projects to determine the exact IAM permissions, roles, or policies required by the codebase.

---

## When to Use

- **GCP Code Audit**: Discover exactly what GCP services and methods a Python, Go, or TypeScript application invokes.
- **IAM Permission Mapping**: Map high-level code invocations (e.g., `storage.buckets.create`) to granular IAM permissions before deploying or configuring Service Accounts.
- **Automated Policy Generation**: Generate least-privilege, consolidated GCP IAM V3 Allow Policies tailored to the application's credential provenance (Service Accounts, Users, Impersonation).
- **Security & Access Reviews**: Identify the exact security footprint and credential mechanisms used across the codebase.

---

## Architecture & Workflow

The skill is split into a two-stage pipeline:
1. **Analyzers (`scripts/python/analyzer.py`, `scripts/go/analyzer.go`, `scripts/ts/analyzer.ts`)**: Parse the target project AST/types, resolve fully qualified method names, extract credential provenance, and output structured JSON conforming to `schema.json`.
2. **Policy Generator (`scripts/policy/policy.py`)**: Ingests the JSON call array from the analyzers (via `stdin`), maps methods to IAM permissions using `permissions.py`, resolves attachment points/principals, and outputs consolidated IAM V3 Allow Policies.

---

> [!WARNING]
> **Output Volume & Stream Truncation**: Static analysis scans can generate hundreds of lines of structured JSON data across dozens of detected API usages. Running the analyzer directly to standard output in an agent shell will result in buffer truncation in execution logs. **Always redirect the JSON output to an intermediate scratch file** (e.g., `> /tmp/scan_results.json`) before reading or feeding it into the policy generator.

### 1. End-to-End Pipeline (Recommended for Small Outputs)
Chain the analyzer and policy generator together using standard Unix streams (`stdin`/`stdout`).

#### For Python Projects:
```bash
/Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/python/analyzer.py <path_to_target_project> [python_env_path] | /Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/policy/policy.py [--service-account=my-sa@project.iam.gserviceaccount.com] [--json]
```

#### For Go Projects:
```bash
(cd /Users/petrusca/.agents/skills/iam-policy-lens/scripts/go && go run *.go <absolute_path_to_target_project>) | /Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/policy/policy.py [--service-account=my-sa@project.iam.gserviceaccount.com] [--json]
```

#### For TypeScript / Node.js Projects:
```bash
node /Users/petrusca/.agents/skills/iam-policy-lens/scripts/ts/dist/analyzer.js <path_to_target_project> | /Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/policy/policy.py [--service-account=my-sa@project.iam.gserviceaccount.com] [--json]
```

### 2. Two-Step Execution (Recommended for Auditing & Large Datasets)
Save the analyzer's structured JSON output to an intermediate file to avoid shell buffer truncation and enable compliance auditing or debugging against `schema.json`, then generate policies via file redirection:

```bash
# Step 1: Generate scan artifact in a scratch location
(cd /Users/petrusca/.agents/skills/iam-policy-lens/scripts/go && go run *.go /path/to/project) > /tmp/scan_results.json

# Step 2: Generate IAM policies from artifact
/Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/policy/policy.py < /tmp/scan_results.json
```

---

## Script Running

### Python

#### Agent Execution Context & CWD Independence
- **Working Directory Agnostic**: All scripts in this skill (`analyzer.py`, `policy.py`, etc.) dynamically resolve their own directory paths (`sys.path.append(os.path.dirname(__file__))`). They can be safely executed from any arbitrary `CWD` (such as an agent's active workspace).
- **Self-Contained Environment**: The Python scripts rely exclusively on the virtual environment located at `/Users/petrusca/.agents/skills/iam-policy-lens/.venv`. They do not require activating the environment or setting external environment variables.

#### Absolute Path Execution Templates (For External Agent Invocation)
When invoking this skill from an external workspace, agents should construct absolute paths to both the skill's virtual environment and the script files:
```bash
# Python Project Analysis Pipeline
/Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/python/analyzer.py <target_project_path> | /Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/policy/policy.py
```

### Go

#### Agent Execution Context & Module Isolation
- **Subshell Execution Pattern**: `go run` requires executing directly within its own module directory (`/Users/petrusca/.agents/skills/iam-policy-lens/scripts/go`) to correctly load its local `go.mod` dependencies. However, agent execution tools (`run_command`) restrict the working directory (`Cwd`) to the active workspace.
- To cleanly satisfy both requirements without violating workspace restrictions, **always execute the Go analyzer inside a subshell** `(cd ... && go run ...)` that isolates module resolution across directory boundaries while keeping the primary tool working directory anchored in your workspace:

```bash
# Executed from any workspace CWD
(cd /Users/petrusca/.agents/skills/iam-policy-lens/scripts/go && go run *.go <absolute_target_project_path>) > /tmp/go_scan.json
```

### TypeScript

#### Agent Execution Context & CWD Independence
- **Working Directory Agnostic**: The compiled TypeScript analyzer (`scripts/ts/dist/analyzer.js`) uses `path.resolve` to handle target project paths and can be safely executed from any arbitrary `CWD`.
- **Self-Contained Environment**: The TypeScript analyzer executes via `node` and relies on the local `node_modules` installed at `/Users/petrusca/.agents/skills/iam-policy-lens/scripts/ts/node_modules`. It does not require global packages or external environment variables. *(Note: Ensure `npm --prefix /Users/petrusca/.agents/skills/iam-policy-lens/scripts/ts run build` has been executed if modifying the analyzer).*

#### Absolute Path Execution Templates (For External Agent Invocation)
When invoking this skill from an external workspace, agents should construct absolute paths to the compiled JavaScript analyzer and the Python virtual environment:
```bash
# TypeScript Project Analysis Pipeline
node /Users/petrusca/.agents/skills/iam-policy-lens/scripts/ts/dist/analyzer.js <target_project_path> | /Users/petrusca/.agents/skills/iam-policy-lens/.venv/bin/python3 /Users/petrusca/.agents/skills/iam-policy-lens/scripts/policy/policy.py
```

---

## Analyzing Results

### 1. Analyzer JSON Output (`schema.json`)
The analyzer emits a clean JSON array of detected calls to `stdout` (while logging progress to `stderr`):

```json
[
  {
    "fullname": "google.cloud.asset_v1.AssetServiceClient.list_assets",
    "file_path": "/path/to/tools/assets.py",
    "line": 32,
    "source_line": "for asset in client.list_assets(request=request):",
    "resolution": "jedi",
    "credentials": {
      "source": "default/implicit",
      "provenance": "IMPLICIT",
      "identity": "APP"
    }
  }
]
```

### 2. Generated IAM V3 Policy Output
The policy generator consolidates permissions by attachment point and principal:

```json
====================================================
🔒 Generated GCP IAM V3 Allow Policies
====================================================

📍 Attachment Point: projects/{project_id}
{
    "name": "policies/projects/{project_id}/allowpolicies/workload-policy",
    "displayName": "Consolidated Workload Allow Policy",
    "rules": [
        {
            "description": "Allow workload permissions for principal://iam.googleapis.com/projects/-/serviceAccounts/your-service-account@your-project.iam.gserviceaccount.com",
            "allowRule": {
                "allowPrincipals": [
                    "principal://iam.googleapis.com/projects/-/serviceAccounts/your-service-account@your-project.iam.gserviceaccount.com"
                ],
                "allowPermissions": [
                    "bigquery.jobs.create",
                    "bigquery.tables.list",
                    "cloudasset.assets.searchAllResources",
                    "compute.instances.list",
                    "container.clusters.list"
                ]
            }
        }
    ]
}
====================================================
```

---

## Troubleshooting & Fallbacks

- **Unresolved Python Types (`Any` or `[fallback]`)**:
  If Jedi cannot find type definitions for external client libraries, provide the path to the target project's virtual environment as the second parameter to `analyzer.py`:
  ```bash
  ./.venv/bin/python3 scripts/python/analyzer.py /path/to/project /path/to/project/.venv/bin/python | ./.venv/bin/python3 scripts/policy/policy.py
  ```
- **Go Package Compilation Warnings**:
  The Go analyzer uses `golang.org/x/tools/go/packages` and will gracefully attempt to scan ASTs even if the target project has partial compilation errors.
