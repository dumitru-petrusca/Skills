import ast
import jedi
import unittest
from typing import Optional

# Ensure we import from the current folder
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from credentials import (
    CredentialProvenance,
    IdentityContext,
    classify_provenance,
    get_base_name_node,
    extract_credentials_from_call,
    trace_credentials,
)

class TestCredentials(unittest.TestCase):
    
    def test_classify_provenance_by_fqn(self):
        # Test exact FQN matching
        self.assertEqual(
            classify_provenance("", "google.oauth2.service_account.Credentials.from_service_account_file"),
            CredentialProvenance.SA_EXPLICIT
        )
        self.assertEqual(
            classify_provenance("", "google.auth.default"),
            CredentialProvenance.SA_DEFAULT
        )
        self.assertEqual(
            classify_provenance("", "google.auth.compute_engine.Credentials"),
            CredentialProvenance.SA_DEFAULT
        )
        self.assertEqual(
            classify_provenance("", "google.auth.impersonated_credentials.Credentials"),
            CredentialProvenance.IMPERSONATION
        )

    def test_classify_provenance_by_source(self):
        # Test source fallback
        self.assertEqual(
            classify_provenance("service_account.Credentials.from_service_account_file('key.json')"),
            CredentialProvenance.SA_EXPLICIT
        )
        self.assertEqual(
            classify_provenance("google.auth.default()"),
            CredentialProvenance.SA_DEFAULT
        )
        
    def test_classify_provenance_default_special_boundary(self):
        # "default" should only match if it relates to google.auth/auth.default
        self.assertEqual(
            classify_provenance("default()"),
            CredentialProvenance.UNKNOWN
        )
        self.assertEqual(
            classify_provenance("google.auth.default()"),
            CredentialProvenance.SA_DEFAULT
        )
        self.assertEqual(
            classify_provenance("auth.default()"),
            CredentialProvenance.SA_DEFAULT
        )

    def test_get_base_name_node(self):
        # Variable name
        tree1 = ast.parse("client")
        base1 = get_base_name_node(tree1.body[0].value)
        self.assertIsNotNone(base1)
        self.assertEqual(base1.id, "client")
        
        # Simple attribute access
        tree2 = ast.parse("self.client")
        base2 = get_base_name_node(tree2.body[0].value)
        self.assertIsNotNone(base2)
        self.assertEqual(base2.id, "self")
        
        # Nested attribute access
        tree3 = ast.parse("my_obj.nested.client")
        base3 = get_base_name_node(tree3.body[0].value)
        self.assertIsNotNone(base3)
        self.assertEqual(base3.id, "my_obj")

    def test_implicit_credentials_tracing(self):
        # Scenario: Implicit default/implicit credentials (no credentials parameter)
        code = """from google.cloud import container_v1
client = container_v1.ClusterManagerClient()
response = client.list_clusters(parent="foo")
"""
        tree = ast.parse(code)
        script = jedi.Script(code)
        
        target_node = self._find_call_node(tree, "list_clusters")
        self.assertIsNotNone(target_node, "Target list_clusters call node not found in AST")
        res = trace_credentials(target_node.func.value, script, tree)
        self.assertIsNotNone(res)
        self.assertEqual(res.source, "default/implicit")
        self.assertEqual(res.provenance, CredentialProvenance.IMPLICIT)
        self.assertEqual(res.identity, IdentityContext.APP)

    def test_explicit_file_credentials_tracing(self):
        # Scenario: Explicit service account key file referenced via a variable
        code = """from google.cloud import container_v1
from google.oauth2 import service_account
credentials = service_account.Credentials.from_service_account_file("key.json")
client = container_v1.ClusterManagerClient(credentials=credentials)
response = client.list_clusters(parent="foo")
"""
        tree = ast.parse(code)
        script = jedi.Script(code)
        
        target_node = self._find_call_node(tree, "list_clusters")
        self.assertIsNotNone(target_node, "Target list_clusters call node not found in AST")
        res = trace_credentials(target_node.func.value, script, tree)
        self.assertIsNotNone(res)
        self.assertEqual(res.source, "service_account.Credentials.from_service_account_file('key.json')")
        self.assertEqual(res.provenance, CredentialProvenance.SA_EXPLICIT)
        self.assertEqual(res.identity, IdentityContext.APP)

    def test_inline_credentials_tracing(self):
        # Scenario: Explicit service account key file instantiated inline inside the constructor
        code = """from google.cloud import container_v1
from google.oauth2 import service_account
client = container_v1.ClusterManagerClient(
    credentials=service_account.Credentials.from_service_account_file("key.json")
)
response = client.list_clusters(parent="foo")
"""
        tree = ast.parse(code)
        script = jedi.Script(code)
        
        target_node = self._find_call_node(tree, "list_clusters")
        self.assertIsNotNone(target_node, "Target list_clusters call node not found in AST")
        res = trace_credentials(target_node.func.value, script, tree)
        self.assertIsNotNone(res)
        self.assertEqual(res.source, "service_account.Credentials.from_service_account_file('key.json')")
        self.assertEqual(res.provenance, CredentialProvenance.SA_EXPLICIT)
        self.assertEqual(res.identity, IdentityContext.APP)

    def test_module_level_credentials_tracing(self):
        # Scenario: Module-level call (e.g. vertexai.init), uses default credentials
        code = """import vertexai
vertexai.init(project="my-project")
"""
        tree = ast.parse(code)
        script = jedi.Script(code)
        
        target_node = self._find_call_node(tree, "init")
        self.assertIsNotNone(target_node, "Target init call node not found in AST")
        res = trace_credentials(target_node.func.value, script, tree)
        self.assertIsNotNone(res)
        self.assertEqual(res.source, "default/implicit")
        self.assertEqual(res.provenance, CredentialProvenance.IMPLICIT)
        self.assertEqual(res.identity, IdentityContext.APP)

    def _find_call_node(self, tree: ast.AST, method_name: str) -> Optional[ast.Call]:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == method_name:
                return node
        return None

if __name__ == "__main__":
    unittest.main()

