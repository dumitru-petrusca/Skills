from dataclasses import dataclass
from typing import Optional
from credentials import CredentialsInfo
from utils import clean_gapic_fqn

@dataclass
class GapicCall:
    fullname: str
    file_path: str
    line: int
    source_line: str
    resolution: str
    client_fullname: Optional[str] = None
    credentials: Optional[CredentialsInfo] = None

IMPORTS = ["google.cloud", "google.genai", "vertexai", "google.adk"]

def isRelevantImport(import_name: Optional[str]) -> bool:
    return bool(import_name and any(imp in import_name for imp in IMPORTS))
