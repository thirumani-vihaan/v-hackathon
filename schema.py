from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict, Any, get_args
from datetime import datetime, timezone
import uuid

@dataclass
class SensorReading:
    gas_ppm: float
    temp_c: float
    oxygen_pct: float
    humidity_pct: float
    permit_type: str
    worker_count: int
    zone: str
    timestamp: str
    pressure_bar: float = 1.013
    rescue_team_present: bool = True

    def __post_init__(self):
        if not (0 <= self.oxygen_pct <= 100):
            raise ValueError("oxygen_pct must be between 0 and 100")
        if self.gas_ppm < 0:
            raise ValueError("gas_ppm cannot be negative")
        if self.worker_count < 0:
            raise ValueError("worker_count cannot be negative")

    def to_dict(self) -> dict:
        return {
            "gas_ppm": self.gas_ppm,
            "temp_c": self.temp_c,
            "oxygen_pct": self.oxygen_pct,
            "humidity_pct": self.humidity_pct,
            "permit_type": self.permit_type,
            "worker_count": self.worker_count,
            "zone": self.zone,
            "timestamp": self.timestamp,
            "pressure_bar": self.pressure_bar,
            "rescue_team_present": self.rescue_team_present
        }

@dataclass
class Hazard:
    type: Literal['no_helmet', 'smoke_fire', 'unauthorized_person', 'unsafe_equipment', 'gas_leak_visual', 'electrical_hazard']
    confidence: float
    bbox: List[int]  # percentages [x1,y1,x2,y2] 0..100

    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        if len(self.bbox) != 4:
            raise ValueError("bbox must have 4 ints")
        valid_types = get_args(self.__annotations__['type'])
        if self.type not in valid_types:
            raise ValueError(f"Hazard type must be one of {valid_types}, got {self.type}")

@dataclass
class VisionInput:
    image_path: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class SensorInput:
    reading: SensorReading
    active_permits: List[str] = field(default_factory=list)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class QueryInput:
    query_text: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class ComplianceInput:
    sensor: SensorReading
    active_permits: List[str] = field(default_factory=list)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class OrchestratorInput:
    input_type: Literal['image', 'sensor', 'query', 'full_scan']
    data: Dict[str, Any]
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class VisionResult:
    hazards: List[Hazard]
    summary: str
    source: Literal['gemini', 'fallback']
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None

@dataclass
class SafetyAlert:
    risk_score: int
    triggered_rules: List[str]
    recommended_action: str
    zone: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None
    def __post_init__(self):
        self.risk_score = max(0, min(100, self.risk_score))

@dataclass
class ComplianceViolation:
    rule_id: str
    name: str
    severity: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    message: str
    oisd_reference: str

    def __post_init__(self):
        valid_severities = get_args(self.__annotations__['severity'])
        if self.severity not in valid_severities:
            raise ValueError(f"Severity must be one of {valid_severities}, got {self.severity}")

@dataclass
class ComplianceResult:
    pass_status: bool
    violations: List[ComplianceViolation]
    highest_severity: Optional[Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None

@dataclass
class KnowledgeResult:
    answer: str
    sources: List[Dict[str, str]]  # [{filename,page,excerpt}]
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None

@dataclass
class OrchestratorResult:
    request_id: str
    input_type: str
    vision: Optional[VisionResult] = None
    safety: Optional[SafetyAlert] = None
    compliance: Optional[ComplianceResult] = None
    knowledge: Optional[KnowledgeResult] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: Optional[str] = None
