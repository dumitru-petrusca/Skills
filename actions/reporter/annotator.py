"""
GitHub Actions PR Annotator for IAM Policy Lens
================================================
Reads the structured JSON output from the IAM Policy Lens analyzers and generates
GitHub Actions inline workflow annotations and job summaries for pull requests.
"""
import os
import sys
import json
import subprocess


def generate_annotations(json_path: str):
    workspace = os.getenv("GITHUB_WORKSPACE", ".")
    
    if not os.path.exists(json_path):
        print(f"Warning: Results file {json_path} does not exist.", file=sys.stderr)
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON results {json_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("Invalid JSON format: Expected a list of GAPIC calls.", file=sys.stderr)
        sys.exit(1)

    changed_files = set()
    try:
        res = subprocess.run(["git", "diff", "--name-only", "HEAD^1"], capture_output=True, text=True, cwd=workspace)
        if res.returncode == 0:
            changed_files = {f.strip() for f in res.stdout.splitlines() if f.strip()}
        else:
            print(f"Debug git diff failed: {res.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not determine changed files: {e}", file=sys.stderr)

    print(f"DEBUG CHANGED FILES: {changed_files}")

    def get_priority(call_obj):
        abs_path = call_obj.get("file_path", "")
        rel_p = os.path.relpath(abs_path, workspace) if abs_path else ""
        return 0 if rel_p in changed_files else 1

    data.sort(key=get_priority)

    summary_lines = [
        "### 🔍 IAM Policy Lens - Scan Results",
        f"**Discovered {len(data)} Google Cloud API invocation(s)** across the codebase.\n",
        "| File | Line | Resolved Method | Client |",
        "| :--- | :---: | :--- | :--- |"
    ]

    for call in data:
        try:
            abs_path = call.get("file_path", "")
            rel_path = os.path.relpath(abs_path, workspace) if abs_path else ""
            line = call.get("line", 0)
            fullname = call.get("fullname", "")
            client = call.get("client_fullname", "N/A") or "N/A"
            source_line = call.get("source_line", "").strip()

            title = "GCP Client Invocation Discovered"
            message = f"{fullname} (Client: {client})"
            if source_line:
                message += f" | Code: {source_line}"

            print(f"DEBUG GAPIC -> rel_path='{rel_path}', line={line}, fqn='{fullname}'")
            # Output GitHub Action Notice string for inline PR annotation
            print(f"::notice file={rel_path},line={line},title={title}::{message}")

            # Append to table for GitHub Step Summary
            summary_lines.append(f"| `{rel_path}` | `{line}` | `{fullname}` | `{client}` |")
        except Exception as e:
            print(f"Warning: Skipping malformed entry: {e}", file=sys.stderr)

    # Write to GITHUB_STEP_SUMMARY if available in environment
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file and os.path.exists(summary_file):
        try:
            with open(summary_file, "a", encoding="utf-8") as sf:
                sf.write("\n".join(summary_lines) + "\n\n")
        except Exception as e:
            print(f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 annotator.py <path_to_json_results>", file=sys.stderr)
        sys.exit(1)

    generate_annotations(sys.argv[1])
