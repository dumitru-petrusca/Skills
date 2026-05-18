#!/usr/bin/env python3
"""
Terraform IAM Least-Privilege Verification Gate
=============================================

This script performs a 100% static, offline audit to verify that the GCP IAM 
permissions granted in your Terraform configurations (.tf files) fully cover 
the required permissions detected in your application code by Policy Lens.

It requires no cloud credentials or network access, and can generate inline 
GitHub Actions annotations to pinpoint exactly where permissions are missing or extra.
"""

import os
import sys
import json
import argparse
import re
from terraform import get_granted_permissions, find_permission_locations


def resolve_relative_path(file_path, workspace):
    """Resolves a file path robustly to a relative path from workspace, handling potential ../ prefixes."""
    if not file_path:
        return "N/A"
    resolved_path = file_path
    if not os.path.isabs(resolved_path):
        cwd_path = os.path.abspath(resolved_path)
        if os.path.exists(cwd_path):
            resolved_path = cwd_path
        else:
            ws_path = os.path.abspath(os.path.join(workspace, resolved_path))
            if os.path.exists(ws_path):
                resolved_path = ws_path
            else:
                stripped_path = resolved_path
                while stripped_path.startswith('../'):
                    stripped_path = stripped_path[3:]
                ws_stripped = os.path.abspath(os.path.join(workspace, stripped_path))
                if os.path.exists(ws_stripped):
                    resolved_path = ws_stripped
    return os.path.relpath(resolved_path, workspace)


def get_required_permissions(policy_json_path):
    """Reads required permissions from the Policy Lens JSON artifact (Consolidated IAM V3 Allow Policies)."""
    with open(policy_json_path, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON block by finding lines that start/end with JSON markers
        lines = content.splitlines()
        start_idx = -1
        end_idx = -1
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if start_idx == -1 and (stripped.startswith('{') or stripped.startswith('[')):
                start_idx = idx
            if start_idx != -1 and (stripped.startswith('}') or stripped.startswith(']')):
                end_idx = idx

        if start_idx != -1 and end_idx != -1:
            try:
                json_str = "\n".join(lines[start_idx:end_idx+1])
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"Error: Failed to parse extracted JSON block: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: Policy Lens JSON is not valid JSON and no JSON block found.", file=sys.stderr)
            sys.exit(1)



    required = set()

    # Normalize input data to a list of policy items
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
    else:
        print("Error: Policy Lens JSON must be a list or dict.", file=sys.stderr)
        sys.exit(1)

    for item in items:
        if not isinstance(item, dict):
            continue
        # Can be nested under "policy" key (generator output) or a direct policy object
        policy = item.get("policy") if "policy" in item else item
        if isinstance(policy, dict):
            for rule in policy.get("rules", []):
                if isinstance(rule, dict):
                    allow_rule = rule.get("allowRule", {})
                    if isinstance(allow_rule, dict):
                        permissions = allow_rule.get("allowPermissions", [])
                        if isinstance(permissions, list):
                            required.update(permissions)

    return required


def get_missing_permission_locations(gapic_calls_path, missing_permissions):
    """Maps each missing permission back to the code locations (file_path, line, gapic_method) that required it."""
    locations = {}  # permission -> list of dict
    if not gapic_calls_path or not os.path.exists(gapic_calls_path):
        return locations

    try:
        # Append target policy dir to sys.path so we can load permissions mapping
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../iam-policy-lens/scripts/policy")))
        from permissions import gapic2permission
    except ImportError:
        print("Warning: Could not import permissions mapper. Inline code annotations for missing permissions will be unavailable.", file=sys.stderr)
        return locations

    try:
        with open(gapic_calls_path, "r", encoding="utf-8") as f:
            calls = json.load(f)

        for call in calls:
            if not isinstance(call, dict):
                continue
            fullname = call.get("fullname")
            if not fullname:
                continue

            perms = gapic2permission(fullname)
            if perms:
                for perm in perms:
                    if perm in missing_permissions:
                        loc = {
                            "file_path": call.get("file_path", ""),
                            "line": call.get("line", 0),
                            "method": fullname,
                            "source_line": call.get("source_line", "").strip()
                        }
                        locations.setdefault(perm, []).append(loc)
    except Exception as e:
        print(f"Warning: Error reading gapic calls for annotations: {e}", file=sys.stderr)

    return locations


def main():
    parser = argparse.ArgumentParser(
        description="Verify if Terraform Custom Roles cover required permissions from Policy Lens."
    )
    parser.add_argument(
        "--tf-dir",
        required=True,
        help="Path to the directory containing your Terraform (.tf) files."
    )
    parser.add_argument(
        "--policy-json",
        required=True,
        help="Path to the Policy Lens JSON file (analyzer or policy generator output)."
    )
    parser.add_argument(
        "--gapic-calls",
        required=False,
        default=None,
        help="Path to the raw GAPIC calls JSON (enables inline code annotations for missing permissions)."
    )
    parser.add_argument(
        "--fail-on-extra",
        action="store_true",
        help="Fail the verification if extra (over-privileged) permissions are granted in Terraform."
    )

    args = parser.parse_args()
    workspace = os.getenv("GITHUB_WORKSPACE", ".")

    print("--------------------------------------------------")
    print("🔒 Running Static IAM Least-Privilege Verification")
    print("--------------------------------------------------")
    print(f"Terraform Directory: {args.tf_dir}")
    print(f"Policy Lens Artifact: {args.policy_json}")
    if args.gapic_calls:
        print(f"GAPIC Calls Artifact: {args.gapic_calls}")
    print("--------------------------------------------------")

    # Extract required permissions from Policy Lens
    try:
        required = get_required_permissions(args.policy_json)
    except Exception as e:
        print(f"Error loading Policy Lens JSON: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract granted permissions from HCL
    granted = get_granted_permissions(args.tf_dir)

    print(f"🔍 Codebase requires:  {sorted(list(required))}")
    print(f"🛡️ Terraform grants:  {sorted(list(granted))}")
    print("--------------------------------------------------")

    # 1. Check for under-privileged (Missing permissions: required but not granted)
    missing = required - granted
    # 2. Check for over-privileged (Extra permissions: granted but not required)
    extra = granted - required

    failed = False
    summary_lines = [
        "### 🔒 IAM Least-Privilege Verification Report",
        f"Verified Terraform configurations against **{len(required)} required permissions**.\n"
    ]

    # Resolve missing permissions source locations if possible
    missing_locs = get_missing_permission_locations(args.gapic_calls, missing)
    tf_locs = find_permission_locations(args.tf_dir)

    if missing:
        failed = True
        print("❌ Under-privileged: Missing permissions detected!", file=sys.stderr)
        summary_lines.append("#### ❌ Under-privileged Permissions (Missing)")
        summary_lines.append("The following required permissions are NOT granted in Terraform HCL:")
        summary_lines.append("| Permission | Required By (Code Location) | Method |")
        summary_lines.append("| :--- | :--- | :--- |")

        for perm in sorted(list(missing)):
            locs = missing_locs.get(perm, [])
            if locs:
                for loc in locs:
                    abs_path = loc["file_path"]
                    rel_path = resolve_relative_path(abs_path, workspace)
                    line = loc["line"]
                    method = loc["method"]
                    
                    # Output inline annotation for GHA
                    print(f"::error file={rel_path},line={line},title=Missing IAM Permission::Code requires permission '{perm}' via '{method}', but it is not granted in Terraform.")
                    summary_lines.append(f"| `{perm}` | `{rel_path}:{line}` | `{method}` |")
            else:
                # Generic fallback annotation
                print(f"::error title=Missing IAM Permission::Required permission '{perm}' is not granted in Terraform.")
                summary_lines.append(f"| `{perm}` | *Location Unknown* | *N/A* |")
        
        summary_lines.append("\n")

    if extra:
        print("⚠️ Over-privileged: Extra permissions detected!", file=sys.stderr)
        log_level = "error" if args.fail_on_extra else "warning"
        if args.fail_on_extra:
            failed = True
            summary_header = "#### ❌ Over-privileged Permissions (Extra - FAILED)"
        else:
            summary_header = "#### ⚠️ Over-privileged Permissions (Extra - Warning)"

        summary_lines.append(summary_header)
        summary_lines.append("The following granted permissions are NOT used by any code:")
        summary_lines.append("| Permission | Granted In (Terraform Location) |")
        summary_lines.append("| :--- | :--- |")

        for perm in sorted(list(extra)):
            locs = tf_locs.get(perm, [])
            if locs:
                for file_path, line in locs:
                    rel_path = resolve_relative_path(file_path, workspace)
                    print(f"::{log_level} file={rel_path},line={line},title=Over-privileged IAM Permission::GCP permission '{perm}' is granted in Terraform but not required by any API calls in the codebase.")
                    summary_lines.append(f"| `{perm}` | `{rel_path}:{line}` |")
            else:
                # Generic fallback annotation
                print(f"::{log_level} title=Over-privileged IAM Permission::Permission '{perm}' is granted in Terraform but not required by any API calls in the codebase.")
                summary_lines.append(f"| `{perm}` | *Location Unknown* |")

        summary_lines.append("\n")

    # If everything is clean
    if not missing and not extra:
        print("✅ Verification Succeeded! All permissions match exactly (least-privilege achieved).")
        summary_lines.append("✅ **Verification Succeeded!** All permissions match exactly (least-privilege achieved).")
    elif not missing and extra and not args.fail_on_extra:
        print("✅ Verification Succeeded! Required permissions are covered. (Warnings generated for extra permissions)")
        summary_lines.append("✅ **Verification Succeeded!** Required permissions are fully covered. (Some over-privileged warnings exist)")

    # Write to GITHUB_STEP_SUMMARY if available
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as sf:
                sf.write("\n".join(summary_lines) + "\n")
        except Exception as e:
            print(f"Warning: Failed to write to GITHUB_STEP_SUMMARY: {e}", file=sys.stderr)

    if failed:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
