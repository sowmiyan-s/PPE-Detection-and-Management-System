"""
Stage 4 – Zone-based rule engine.

Each camera zone has a configured set of required PPE. The rule engine
evaluates a worker's detected equipment against the zone requirements and
returns a compliance result describing which items are present, absent, and
whether the worker is compliant.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from src.core import config


@dataclass
class ComplianceResult:
    worker_id: int
    zone: str
    required_ppe: set[str]
    detected_ppe: set[str]
    missing_ppe: set[str]
    extra_ppe: set[str]      # present but not required (informational)
    compliant: bool
    confidence: float        # mean confidence of detected PPE items


@dataclass
class ZoneConfig:
    """Runtime-mutable zone configuration (loaded from DB or config.py)."""
    name: str
    required_ppe: set[str]
    description: str = ""
    authorised_workers: set[str] = field(default_factory=set)
    frame_threshold: int = 8
    dwell_seconds: int = 2
    confidence: float = 0.60

    def check_compliance(
        self,
        worker_id: int | str,
        detected_ppe: set[str],
        confidence: float = 1.0,
    ) -> ComplianceResult:
        aliases = getattr(config, "PPE_ALIASES", {})
        norm_required = {aliases.get(i, i): i for i in self.required_ppe}
        norm_detected = {aliases.get(i, i): i for i in detected_ppe}

        norm_missing_keys = set(norm_required.keys()) - set(norm_detected.keys())
        norm_extra_keys   = set(norm_detected.keys()) - set(norm_required.keys())

        missing = {norm_required[k] for k in norm_missing_keys}
        extra   = {norm_detected[k] for k in norm_extra_keys}

        # Check restricted zone authorization if configured
        w_str = f"Worker-{worker_id}" if isinstance(worker_id, int) else str(worker_id)
        if self.authorised_workers and w_str not in self.authorised_workers:
            missing.add("unauthorised_entry")

        return ComplianceResult(
            worker_id=worker_id if isinstance(worker_id, int) else 0,
            zone=self.name,
            required_ppe=set(self.required_ppe),
            detected_ppe=set(detected_ppe),
            missing_ppe=missing,
            extra_ppe=extra,
            compliant=len(missing) == 0,
            confidence=confidence,
        )


class RuleEngine:
    """
    Manages multiple zone configurations and evaluates worker compliance.

    Usage
    -----
    engine = RuleEngine()
    result = engine.evaluate(worker_id=101, zone="work_at_height",
                             detected_ppe={"helmet", "vest", "boots"},
                             confidence=0.85)
    if not result.compliant:
        print(result.missing_ppe)
    """

    def __init__(self, zones: Optional[dict[str, ZoneConfig]] = None):
        if zones is not None:
            self._zones = zones
        else:
            self._zones = {
                name: ZoneConfig(name=name, required_ppe=set(required))
                for name, required in config.ZONE_RULES.items()
            }

    # ── Public API ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        worker_id: int,
        detected_ppe: set[str],
        zone: Optional[str] = None,
        confidence: float = 1.0,
    ) -> ComplianceResult:
        """Return a ComplianceResult for one worker in one zone."""
        zone_name = zone or config.DEFAULT_ZONE
        zone_cfg  = self._zones.get(zone_name)

        if zone_cfg is None:
            # Unknown zone – fall back to default
            zone_cfg = self._zones.get(config.DEFAULT_ZONE, ZoneConfig(
                name=zone_name,
                required_ppe=set(config.ZONE_RULES.get(
                    config.DEFAULT_ZONE, {"helmet", "vest"}
                )),
            ))

        return zone_cfg.check_compliance(
            worker_id=worker_id,
            detected_ppe=detected_ppe,
            confidence=confidence,
        )

    def add_zone(
        self,
        name: str,
        required_ppe: set[str],
        description: str = "",
        frame_threshold: int = 8,
        dwell_seconds: int = 2,
        confidence: float = 0.60,
    ) -> None:
        """Add or replace a zone at runtime (e.g. loaded from DB)."""
        self._zones[name] = ZoneConfig(
            name=name,
            required_ppe=required_ppe,
            description=description,
            frame_threshold=frame_threshold,
            dwell_seconds=dwell_seconds,
            confidence=confidence,
        )

    def remove_zone(self, name: str) -> bool:
        return self._zones.pop(name, None) is not None

    def list_zones(self) -> list[dict]:
        return [
            {
                "id": z.name,
                "name": z.name,
                "required_ppe": sorted(z.required_ppe),
                "description": z.description,
                "frame_threshold": z.frame_threshold,
                "frameThreshold": z.frame_threshold,
                "dwell_seconds": z.dwell_seconds,
                "dwellSeconds": z.dwell_seconds,
                "confidence": z.confidence,
                "confidence_threshold": z.confidence,
            }
            for z in self._zones.values()
        ]

    def get_zone(self, name: str) -> Optional[ZoneConfig]:
        return self._zones.get(name)
