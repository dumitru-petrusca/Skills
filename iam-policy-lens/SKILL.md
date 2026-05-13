---
name: iam-policy-lens
description: Python Cloud Access Scanner to statically identify Google Cloud (GAPIC) and Google API client library invocations, helping map and determine the IAM permissions required by the codebase.
---

# IAM Policy Lens Instructions

Use this skill when you need to audit, analyze, or map Google Cloud API (GAPIC) usage in a Python project to determine the required IAM permissions, roles, or policies.

---

## When to Use

- **GCP Code Audit**: When asked to discover what GCP services a Python application uses.
- **IAM Permission Mapping**: Before deploying an application or when configuring a Service Account to determine the exact permissions (e.g., `storage.buckets.create`) required.
- **Security & Access Reviews**: To identify potential security footprints and API calls made by the codebase.

---

## Execution
Run the analyzer on the target project directory using the copied script:
```bash
/Users/petrusca/Google/policy-lens/.venv/bin/python3 scripts/python/analyzer.py <path_to_target_project> [python_env_path]
```

- **`<path_to_target_project>`**: The absolute or relative path of the Python repository you wish to scan.
- **`[python_env_path]`** (Optional): Path to the Python executable of the target project's virtual environment (helps the engine resolve external library stubs).

### Analyzing Results
The output lists detected API calls grouped by file, along with their line number, original code snippet, fully qualified method path, and the resolution engine.


#### Example Output:
```text
📄 File: /Users/petrusca/Google/gcp_python_iam_analyzer/gcp_cost_optimizer_agent/deploy.py
     deploy.py:56: `vertexai.init(project=PROJECT, location=LOCATION)`
     Method: google.cloud.aiplatform.initializer._Config.init [jedi]

📄 File: /Users/petrusca/Google/gcp_python_iam_analyzer/gcp_cost_optimizer_agent/tools/assets.py
     tools/assets.py:32: `for asset in client.list_assets(request=request):`
     Method: google.cloud.asset_v1.AssetServiceClient.list_assets [jedi]
```

---

## Troubleshooting & Fallbacks

- **Unresolved Types (`Any` or `[fallback]`)**:
  If Jedi cannot find type definitions for external client libraries, provide the path to the target project's virtual environment as the third parameter:
  ```bash
  /Users/petrusca/Google/policy-lens/.venv/bin/python3 scripts/python/analyzer.py /path/to/project /path/to/project/.venv/bin/python
  ```
