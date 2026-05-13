import ast
import jedi
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple
from utils import get_base_name_node

class CredentialProvenance(str, Enum):
    """Represents the security provenance/classification of the credentials used.
    
    SA_DEFAULT: Application Default Credentials (ADC) or Compute Engine metadata server.
    SA_EXPLICIT: Explicit Service Account keys (either loaded from a JSON file or JSON dict).
    OAUTH_USER: OAuth2 user credentials (usually saved local tokens).
    OAUTH_FLOW: OAuth2 authentication flow (typically InstalledAppFlow or Flow).
    DWD: Domain-Wide Delegation.
    IMPERSONATION: Service Account impersonation or ID Token credentials.
    IMPLICIT: No credentials parameter passed (defaults to Application Default Credentials).
    UNKNOWN: Unable to statically classify.
    """
    SA_DEFAULT = "SA_DEFAULT"
    SA_EXPLICIT = "SA_EXPLICIT"
    OAUTH_USER = "OAUTH_USER"
    OAUTH_FLOW = "OAUTH_FLOW"
    DWD = "DWD"
    IMPERSONATION = "IMPERSONATION"
    IMPLICIT = "IMPLICIT"
    UNKNOWN = "UNKNOWN"

class IdentityContext(str, Enum):
    """Simplified identity category for security audits and policy enforcement.
    
    APP: Represents application-level service identities.
    USER: Represents end-user delegated credentials.
    IMPERSONATED: Represents delegated or impersonated service identities.
    UNKNOWN: Unable to determine identity scope.
    """
    APP = "APP"
    USER = "USER"
    IMPERSONATED = "IMPERSONATED"
    UNKNOWN = "UNKNOWN"

def to_identity_context(prov: CredentialProvenance) -> IdentityContext:
    """Maps a detailed CredentialProvenance to a simplified IdentityContext."""
    if prov in (
        CredentialProvenance.SA_DEFAULT,
        CredentialProvenance.SA_EXPLICIT,
        CredentialProvenance.IMPLICIT,
    ):
        return IdentityContext.APP
    if prov in (
        CredentialProvenance.OAUTH_USER,
        CredentialProvenance.OAUTH_FLOW,
    ):
        return IdentityContext.USER
    if prov in (
        CredentialProvenance.DWD,
        CredentialProvenance.IMPERSONATION,
    ):
        return IdentityContext.IMPERSONATED
    return IdentityContext.UNKNOWN

@dataclass
class CredentialsInfo:
    """Holds security information about the credentials parsed from client instantiation."""
    source: str
    provenance: CredentialProvenance
    identity: Optional[IdentityContext] = None
    
    def __post_init__(self):
        if self.identity is None:
            self.identity = to_identity_context(self.provenance)

# Prioritized substring patterns matching resolved fully-qualified names (FQNs)
# or code expressions to their respective CredentialProvenance.
_CREDENTIAL_PATTERNS = [
    # SA default credentials / Application Default Credentials (ADC)
    ("google.auth.default", CredentialProvenance.SA_DEFAULT),
    ("auth.default", CredentialProvenance.SA_DEFAULT),
    ("default", CredentialProvenance.SA_DEFAULT),
    
    # Explicit service account key files or dictionaries
    ("service_account.Credentials.from_service_account_info", CredentialProvenance.SA_EXPLICIT),
    ("service_account.Credentials.from_service_account_file", CredentialProvenance.SA_EXPLICIT),
    ("Credentials.from_service_account_info", CredentialProvenance.SA_EXPLICIT),
    ("Credentials.from_service_account_file", CredentialProvenance.SA_EXPLICIT),
    
    # OAuth2 user credentials (user consent flow saved tokens)
    ("Credentials.from_authorized_user_file", CredentialProvenance.OAUTH_USER),
    ("Credentials.from_authorized_user_info", CredentialProvenance.OAUTH_USER),
    
    # Compute Engine metadata server ADC variant
    ("compute_engine.Credentials", CredentialProvenance.SA_DEFAULT),
    
    # Impersonated service account credentials
    ("impersonated_credentials.Credentials", CredentialProvenance.IMPERSONATION),
    ("IDTokenCredentials", CredentialProvenance.IMPERSONATION),
]

# Patterns representing OAuth2 authentication flows
_OAUTH_FLOW_PATTERNS = (
    "Flow.from_client_config",
    "Flow.from_client_secrets_file",
    "AppFlow.from_client_secrets_file",
    "AppFlow.from_client_config",
    "InstalledAppFlow.from_client_secrets_file",
    ".run_local_server",
    ".run_console",
)

def classify_provenance(source_code: str, fqn: Optional[str] = None) -> CredentialProvenance:
    """Classifies the provenance of a credential initialization.
    
    It first checks the Jedi-resolved FQN (fully qualified name) if available.
    If the FQN does not yield a match, it falls back to source-code substring matching.
    """
    # 1. Domain-Wide Delegation check (.with_subject)
    if fqn and fqn.endswith(".with_subject"):
        return CredentialProvenance.DWD
    if "with_subject" in source_code:
        return CredentialProvenance.DWD

    # 2. OAuth Flow checks
    if fqn and any(p in fqn for p in _OAUTH_FLOW_PATTERNS):
        return CredentialProvenance.OAUTH_FLOW
    if any(p in source_code for p in _OAUTH_FLOW_PATTERNS):
        return CredentialProvenance.OAUTH_FLOW

    # 3. Check Jedi FQN (highly accurate standard patterns)
    if fqn:
        for pattern, provenance in _CREDENTIAL_PATTERNS:
            if pattern in fqn:
                return provenance
                
    # 4. Fallback to source code string matching
    for pattern, provenance in _CREDENTIAL_PATTERNS:
        if pattern in source_code:
            # Special check: "default" is a generic word; only match it
            # if it belongs to a google auth environment.
            if pattern == "default" and not ("google.auth" in source_code or "auth.default" in source_code or "google.auth.default" in source_code):
                continue
            return provenance
            
    return CredentialProvenance.UNKNOWN


def extract_credentials_from_call(call_node: ast.Call, script: jedi.Script, tree: ast.AST) -> CredentialsInfo:
    """Extracts the credentials source expression and classifies its provenance from a client constructor call.
    
    1. Searches for the 'credentials' keyword argument in the call.
    2. If missing, returns "default/implicit" mapping to IMPLICIT (ADC).
    3. Uses Jedi to infer the FQN of the credentials expression.
    4. Traces variables (ast.Name) back to their initial assignment to extract the source code.
    5. Otherwise, returns the unparsed inline expression.
    """
    # 1. Locate the 'credentials' parameter in the keywords list
    cred_expr = None
    for kw in call_node.keywords:
        if kw.arg == 'credentials':
            cred_expr = kw.value
            break
            
    # If no credentials argument is passed, the client library implicitly defaults to ADC
    if not cred_expr:
        return CredentialsInfo(
            source="default/implicit",
            provenance=CredentialProvenance.IMPLICIT
        )
        
    # 2. Use Jedi's infer to resolve the fully qualified name (FQN) of the credentials creation
    cred_fqn = None
    try:
        inferences = script.infer(cred_expr.lineno, cred_expr.col_offset)
        if inferences:
            cred_fqn = inferences[0].full_name
    except Exception:
        pass
        
    # 3. If the credentials argument is a variable (ast.Name), trace where it is assigned
    if isinstance(cred_expr, ast.Name):
        cred_defs = script.goto(cred_expr.lineno, cred_expr.col_offset)
        if cred_defs:
            cred_def = cred_defs[0]
            cred_assign = None
            # Locate the ast.Assign node corresponding to the definition line
            for n in ast.walk(tree):
                if isinstance(n, ast.Assign) and n.lineno == cred_def.line:
                    cred_assign = n
                    break
            if cred_assign:
                source_str = ast.unparse(cred_assign.value).strip()
                provenance = classify_provenance(source_str, cred_fqn)
                return CredentialsInfo(source=source_str, provenance=provenance)
            else:
                # Fallback if it's defined as a parameter or in an external scope
                source_str = f"passed as argument (defined at line {cred_def.line})"
                provenance = classify_provenance(source_str, cred_fqn)
                return CredentialsInfo(source=source_str, provenance=provenance)
                
    # 4. If it is an inline constructor or direct function call, return it directly
    source_str = ast.unparse(cred_expr).strip()
    provenance = classify_provenance(source_str, cred_fqn)
    return CredentialsInfo(source=source_str, provenance=provenance)

def trace_credentials(client_node: ast.AST, script: jedi.Script, tree: ast.AST) -> Optional[CredentialsInfo]:
    """Traces a client instance variable to retrieve the credentials used for its initialization.
    
    1. Resolves the base variable of the client node.
    2. If the base variable resolves to an imported module (direct module-level calls), returns default/implicit.
    3. Finds the ast.Assign node where the client variable was initialized.
    4. Delegates to extract_credentials_from_call to analyze the constructor parameters.
    """
    # 1. Retrieve root variable Name node
    base_node = get_base_name_node(client_node)
    if not base_node:
        return None
        
    # 2. Find where the variable is defined
    defs = script.goto(base_node.lineno, base_node.col_offset)
    if not defs:
        return None
        
    def_node = defs[0]
    # If the variable is a module name (e.g., vertexai.init), it uses implicit default credentials
    if def_node.type == 'module':
        return CredentialsInfo(
            source="default/implicit",
            provenance=CredentialProvenance.IMPLICIT
        )
        
    # 3. Find the assignment node at that definition line
    assign_node = None
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and n.lineno == def_node.line:
            assign_node = n
            break
            
    # If variable is a parameter or assigned via complex call, we show where it was declared
    if not assign_node or not isinstance(assign_node.value, ast.Call):
        return CredentialsInfo(
            source=f"defined at line {def_node.line}",
            provenance=CredentialProvenance.UNKNOWN
        )
        
    # 4. Extract and classify credentials from the constructor call
    return extract_credentials_from_call(assign_node.value, script, tree)
