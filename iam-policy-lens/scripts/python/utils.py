import ast
from typing import Optional

def get_base_name_node(node: ast.AST) -> Optional[ast.Name]:
    """Retrieves the root/base Name node from a potentially nested attribute access.
    
    For example:
      - For `client`, returns `client` (ast.Name)
      - For `self.client`, returns `self` (ast.Name)
      - For `nested.client`, returns `nested` (ast.Name)
      
    This allows the resolver to trace the root variable back to its declaration.
    """
    curr = node
    while isinstance(curr, ast.Attribute):
        curr = curr.value
    if isinstance(curr, ast.Name):
        return curr
    return None

def clean_gapic_fqn(name: str) -> str:
    """Removes internal package structures like .services.[...].client."""
    import re
    name = re.sub(r'\.services\.[a-zA-Z0-9_]+\.client\.', '.', name)
    name = re.sub(r'\.client\.Client', '.Client', name)
    return name
