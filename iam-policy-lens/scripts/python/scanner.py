import ast
import os
import jedi
from gapic import GapicCall, clean_gapic_fqn, isRelevantImport
from typing import List, Optional, Tuple
from credentials import trace_credentials, extract_credentials_from_call


EXCLUDE_DIRS = {".venv", "venv", ".git", ".mypy_cache", "__pycache__", "build", "dist", "node_modules"}


def find_gapic_calls(sources_path: str, python_env: str = None) -> List[GapicCall]:
    """
    Analyzes a Python project using Jedi and returns a list of GapicCall objects.
    """
    
    env = None
    if python_env:
        try:
            env = jedi.create_environment(python_env)
            print(f"Using Jedi environment: {python_env}")
        except Exception as e:
            print(f"Error creating Jedi environment for {python_env}: {e}")
            print("Falling back to default environment.")
            
    project = jedi.Project(sources_path)   
    
    all_calls = []
    for root, dirs, files in os.walk(sources_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                all_calls.extend(scan_file(file_path, project, sources_path, env))
                
    return all_calls


def scan_file(file_path: str, project: jedi.Project, sources_path: str, env) -> List[GapicCall]:
    calls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
        tree = ast.parse(content)
        script = jedi.Script(content, path=file_path, project=project, environment=env)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call = _resolve_gapic_call(node, script, file_path, lines, tree)
                if call:
                    calls.append(call)
    except Exception as e:
        print(f"Error scanning {file_path}: {e}")
    return calls



def _resolve_gapic_call(node: ast.Call, script: jedi.Script, file_path: str, lines: List[str], tree: ast.AST) -> Optional[GapicCall]:
    if not (hasattr(node.func, 'end_lineno') and hasattr(node.func, 'end_col_offset')):
        return None
        
    # Point Jedi to the end of the callee name to resolve the method
    line = node.func.end_lineno
    col = node.func.end_col_offset - 1
    inferences = script.infer(line, col)
    
    for inf in inferences:
        fqn = inf.full_name
        if fqn:
            fqn = clean_gapic_fqn(fqn)
        if fqn and isRelevantImport(fqn):
            parent_context = inf.parent()
            client_fqn = clean_gapic_fqn(parent_context.full_name) if parent_context else None
            
            # Trace the credentials used for the client depending on if it's a class instantiation or method call
            credentials_info = None
            if inf.type == 'class':
                credentials_info = extract_credentials_from_call(node, script, tree)
            elif isinstance(node.func, ast.Attribute):
                credentials_info = trace_credentials(node.func.value, script, tree)
                
            return GapicCall(
                fullname=fqn,
                file_path=file_path,
                line=node.lineno,
                source_line=lines[node.lineno - 1].strip(),
                resolution="jedi",
                client_fullname=client_fqn,
                credentials=credentials_info
            )
            
    return None
