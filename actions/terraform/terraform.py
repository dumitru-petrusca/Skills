#!/usr/bin/env python3
"""
Terraform Static Parser Utility
==============================

This module provides 100% static, offline utilities to parse Terraform HCL configurations
without requiring network, providers, state, or cloud credentials.
"""

import os
import sys
import re
import hcl2


def get_granted_permissions(tf_dir):
    """Statically parses all .tf files in a directory to extract permissions defined in custom roles."""
    granted = set()

    if not os.path.exists(tf_dir):
        print(f"Error: Terraform directory '{tf_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    for filename in sorted(os.listdir(tf_dir)):
        if filename.endswith(".tf"):
            file_path = os.path.join(tf_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    tf_content = hcl2.load(f)

                # Parse the HCL resource definitions
                for resource in tf_content.get("resource", []):
                    if "google_project_iam_custom_role" in resource:
                        role_block = list(resource["google_project_iam_custom_role"].values())[0]
                        permissions = role_block.get("permissions", [])
                        if isinstance(permissions, list):
                            granted.update(permissions)
            except Exception as e:
                print(f"Warning: Error parsing HCL from {filename}: {e}", file=sys.stderr)

    return granted


def find_permission_locations(tf_dir):
    """Statically scans all .tf files in tf_dir to map each granted permission to its file and line number."""
    locations = {}  # permission -> list of (file_path, line_number)

    if not os.path.exists(tf_dir):
        return locations

    for filename in sorted(os.listdir(tf_dir)):
        if filename.endswith(".tf"):
            file_path = os.path.join(tf_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                in_custom_role = False
                brace_count = 0

                for idx, line in enumerate(lines):
                    line_num = idx + 1
                    # Check for start of custom role block
                    if re.search(r'resource\s+"google_project_iam_custom_role"\s+"[^"]+"\s*\{', line):
                        in_custom_role = True
                        brace_count = 1
                        continue

                    if in_custom_role:
                        # Keep track of braces to know when block ends
                        brace_count += line.count('{')
                        brace_count -= line.count('}')

                        if brace_count <= 0:
                            in_custom_role = False
                            continue

                        # Look for permissions listed inside the custom role block
                        perms = re.findall(r'"([^"]+)"', line)
                        for perm in perms:
                            if "." in perm:
                                locations.setdefault(perm, []).append((file_path, line_num))
            except Exception as e:
                print(f"Warning: Error parsing locations from {filename}: {e}", file=sys.stderr)

    return locations

