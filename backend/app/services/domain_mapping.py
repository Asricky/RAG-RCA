import json
import threading
from pathlib import Path

from ..config import settings


class DomainMappingService:
    """Resolve KPI relationships from editable, deterministic JSON configuration."""

    def __init__(self, kpi_path: Path | None = None, interface_path: Path | None = None):
        domain_dir = settings.domain_config_dir
        self.kpi_path = kpi_path or domain_dir / "kpi_mapping.json"
        self.interface_path = interface_path or domain_dir / "interface_mapping.json"
        self._lock = threading.Lock()
        self._signature: tuple[int, int] | None = None
        self._kpis: dict[str, dict] = {}
        self._interfaces: dict[str, list[str]] = {}

    def _refresh(self) -> None:
        signature = (self.kpi_path.stat().st_mtime_ns, self.interface_path.stat().st_mtime_ns)
        if signature == self._signature:
            return
        with self._lock:
            if signature == self._signature:
                return
            kpis = json.loads(self.kpi_path.read_text(encoding="utf-8"))
            interfaces = json.loads(self.interface_path.read_text(encoding="utf-8"))
            if not isinstance(kpis, dict) or not isinstance(interfaces, dict):
                raise RuntimeError("Domain mapping files must contain JSON objects")
            self._kpis = {str(name).upper(): dict(value) for name, value in kpis.items()}
            self._interfaces = {
                str(name).upper(): list(dict.fromkeys(str(component).upper() for component in value))
                for name, value in interfaces.items()
            }
            missing = sorted({interface for value in self._kpis.values() for interface in value.get("related_interfaces", [])} - set(self._interfaces))
            if missing:
                raise RuntimeError(f"KPI mappings reference unknown interfaces: {', '.join(missing)}")
            self._signature = signature

    def components_for_interface(self, interface: str) -> list[str]:
        self._refresh()
        return list(self._interfaces.get(str(interface).upper(), []))

    def resolve(self, kpi_name: str | None) -> dict:
        self._refresh()
        key = str(kpi_name or "").upper()
        mapping = self._kpis.get(key, {})
        interfaces = list(dict.fromkeys(str(item).upper() for item in mapping.get("related_interfaces", [])))
        components = sorted({component for interface in interfaces for component in self._interfaces.get(interface, [])})
        return {
            "kpi_name": key or None,
            "kpi_level": mapping.get("level"),
            "related_interfaces": interfaces,
            "related_components": components,
        }

    def enrich(self, kpi_name: str | None, *, kpi_level=None, related_interfaces=None, related_components=None) -> dict:
        resolved = self.resolve(kpi_name)
        if not resolved["related_interfaces"]:
            resolved["related_interfaces"] = list(dict.fromkeys(str(item).upper() for item in (related_interfaces or [])))
        if not resolved["related_components"]:
            resolved["related_components"] = list(dict.fromkeys(str(item).upper() for item in (related_components or [])))
        resolved["kpi_level"] = resolved["kpi_level"] or kpi_level
        return resolved


domain_mapping = DomainMappingService()
