"""
Python Cloud Access Scanner
===========================

Problem Statement:
------------------
This script performs static analysis on a Python codebase to identify Google Cloud, Vertex AI, and Google GenAI client library invocations.
The primary goal is to locate and extract these high-level, Pythonic method calls (e.g., `google.cloud.storage.Client.create_bucket`).

How It Works:
-------------
1. GAPIC Call Extraction (gapic.py): 
    The scanner uses `mypy.build` to generate an Abstract Syntax Tree (AST) of the target project, which handles tricky type-resolution paths.
    It walks the AST looking for `CallExpr` nodes and traces back nested `MemberExpr` chains to resolve fully qualified import names.

How to Run:
-----------
Run the script passing the target repository source path as the first argument:
    .venv/bin/python3 scripts/python/analyzer.py <path_to_project>
    .venv/bin/python3  scripts/python/analyzer.py /Users/petrusca/Google/adk-samples/python/agents/data-science
    .venv/bin/python3 scripts/python/analyzer.py /Users/petrusca/Google/gcp_python_iam_analyzer/gcp_cost_optimizer_agent
"""
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/python/analyzer.py <path_to_project> [python_env_path]")
        sys.exit(1)
        
    project_path = sys.argv[1]
    python_env = sys.argv[2] if len(sys.argv) >= 3 else None
    
    print(f"Scanning: {project_path} for GAPIC calls")
    if python_env:
        print(f"Using Python environment: {python_env}")
        
    start_time = time.time()
    import scanner
    raw_calls = scanner.find_gapic_calls(project_path, python_env)
    elapsed_time = time.time() - start_time
    
    if raw_calls:
        from collections import defaultdict
        grouped_calls = defaultdict(list)
        for call in raw_calls:
            full_path = os.path.abspath(call.file_path)
            grouped_calls[full_path].append(call)
            
        for full_path, calls in sorted(grouped_calls.items()):
            print(f"\n📄 File: {full_path}")
            rel_path = os.path.relpath(full_path, project_path) if os.path.isabs(full_path) else full_path
            for i, call in enumerate(sorted(calls, key=lambda x: x.line)):
                if i > 0:
                    print()
                print(f"     {rel_path}:{call.line}: `{call.source_line}`")
                print(f"     Method: {call.fullname} [{call.resolution}]")
                if getattr(call, 'client_fullname', None):
                    print(f"     Client: {call.client_fullname}")
                if getattr(call, 'credentials', None):
                    print(f"     Credentials: {call.credentials.source}")
                    print(f"     Provenance: {call.credentials.provenance}")
                    print(f"     Identity: {call.credentials.identity}")
                    
                from permissions import gapic2permission
                permissions = gapic2permission(call.fullname)
                if permissions:
                    print(f"     Permissions: {permissions}")
                    
        # Generate and print GCP IAM V3 Allow Policies
        from policy import generate_iam_policies
        import json
        
        print("\n====================================================")
        print("🔒 Generated GCP IAM V3 Allow Policies")
        print("====================================================")
        
        sa_email = os.getenv("GCP_SERVICE_ACCOUNT")
        policies = generate_iam_policies(raw_calls, sa_email)
        for p in policies:
            print(f"\n📍 Attachment Point: {p['attachment_point']}")
            print(json.dumps(p['policy'], indent=4))
    else:
        print("No relevant GAPIC calls found.")
        
    print(f"\nScan completed in {elapsed_time:.2f} seconds.")
    print("====================================================")
