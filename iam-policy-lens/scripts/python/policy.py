import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Set
from gapic import GapicCall
from credentials import CredentialProvenance, IdentityContext
from permissions import gapic2permission


def _resolve_principal(call: GapicCall, default_sa: str = "your-service-account@your-project.iam.gserviceaccount.com") -> str:
    """Resolves the target principal email to bind the policy to, using IAM V3 principal scheme."""
    sa_email = default_sa
    if call.credentials:
        prov = call.credentials.provenance
        source = call.credentials.source
        
        if prov == CredentialProvenance.IMPERSONATION:
            import re
            match = re.search(r"target_principal\s*=\s*['\"]([^'\"]+)['\"]", source)
            if match:
                sa_email = match.group(1)
            else:
                sa_email = "target-impersonated-sa@your-project.iam.gserviceaccount.com"
                
        elif prov in (CredentialProvenance.OAUTH_USER, CredentialProvenance.OAUTH_FLOW):
            return "principalSet://goog/subject/your-user-email@domain.com"
            
    return f"principal://iam.googleapis.com/projects/-/serviceAccounts/{sa_email}"

def _resolve_attachment_point(call: GapicCall) -> str:
    """Determines the target container resource path (attachment point) for the permission."""
    fullname = call.fullname
    
    # Vertex AI (Agent Engines) is regional
    if "aiplatform" in fullname or "vertexai.agent_engines" in fullname:
        return "projects/{project_id}/locations/{location}"
        
    return "projects/{project_id}"

def generate_iam_policies(calls: List[GapicCall], default_sa: str = None) -> List[Dict]:
    """Generates a set of consolidated GCP IAM V3 Allow Policies grouped by attachment point."""
    sa_email = default_sa or "your-service-account@your-project.iam.gserviceaccount.com"
    
    # Structure: attachment_point -> principal -> set of permissions
    policies_map: Dict[str, Dict[str, Set[str]]] = {}
    
    for call in calls:
        permissions = gapic2permission(call.fullname)
        if not permissions:
            continue
            
        principal = _resolve_principal(call, sa_email)
        attachment = _resolve_attachment_point(call)
        
        policies_map.setdefault(attachment, {}).setdefault(principal, set()).update(permissions)
        
    # Convert consolidated maps into GCP IAM V3 Policy JSON format
    generated_policies = []
    
    for attachment, principal_map in sorted(policies_map.items()):
        rules = []
        for principal, permissions in sorted(principal_map.items()):
            rules.append({
                "description": f"Allow workload permissions for {principal}",
                "allowRule": {
                    "allowPrincipals": [principal],
                    "allowPermissions": sorted(list(permissions))
                }
            })
            
        # Map target path to a valid policies resource name
        # E.g. projects/{project_id} -> policies/projects/{project_id}/allowpolicies/workload-policy
        policy_name = f"policies/{attachment}/allowpolicies/workload-policy"
        
        generated_policies.append({
            "attachment_point": attachment,
            "policy": {
                "name": policy_name,
                "displayName": "Consolidated Workload Allow Policy",
                "rules": rules
            }
        })
        
    return generated_policies
