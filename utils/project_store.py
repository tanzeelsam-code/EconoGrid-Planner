"""
Project storage for saved planning workspaces and version history.
"""

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import PROJECTS_DIR


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class ProjectStore:
    """Persist projects as JSON files with simple version history."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or PROJECTS_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> List[Dict[str, Any]]:
        projects = []
        for filepath in sorted(self.base_dir.glob("*.json")):
            project = self._read_project(filepath.stem)
            projects.append(self._project_summary(project))
        return sorted(projects, key=lambda item: item["updated_at"], reverse=True)

    def get_project(self, project_id: str) -> Dict[str, Any]:
        return self._read_project(project_id)

    def save_snapshot(
        self,
        project_name: str,
        module: str,
        inputs: Dict[str, Any],
        results: Dict[str, Any],
        notes: str = "",
    ) -> Dict[str, Any]:
        project_id = self._slugify(project_name)
        existing = self._read_project(project_id, required=False)
        now = _utc_now()

        if existing is None:
            project = {
                "project_id": project_id,
                "project_name": project_name.strip(),
                "created_at": now,
                "updated_at": now,
                "versions": [],
                "latest_by_module": {},
            }
        else:
            project = existing
            project["project_name"] = project_name.strip()
            project["updated_at"] = now

        version_number = len(project["versions"]) + 1
        version_id = f"v{version_number:03d}"
        version = {
            "version_id": version_id,
            "created_at": now,
            "module": module,
            "notes": notes,
            "inputs": deepcopy(inputs),
            "results": deepcopy(results),
            "summary": self._module_summary(module, results),
        }
        project["versions"].append(version)
        project["latest_by_module"][module] = version_id

        self._write_project(project_id, project)
        return project

    def get_versions(self, project_id: str, module: Optional[str] = None) -> List[Dict[str, Any]]:
        project = self.get_project(project_id)
        versions = project["versions"]
        if module:
            versions = [item for item in versions if item["module"] == module]
        return list(reversed(versions))

    def get_latest_version(self, project_id: str, module: str) -> Optional[Dict[str, Any]]:
        project = self.get_project(project_id)
        version_id = project.get("latest_by_module", {}).get(module)
        if not version_id:
            return None
        for version in reversed(project["versions"]):
            if version["version_id"] == version_id:
                return version
        return None

    def _project_summary(self, project: Dict[str, Any]) -> Dict[str, Any]:
        module_counts: Dict[str, int] = {}
        for version in project.get("versions", []):
            module = version["module"]
            module_counts[module] = module_counts.get(module, 0) + 1

        return {
            "project_id": project["project_id"],
            "project_name": project["project_name"],
            "created_at": project["created_at"],
            "updated_at": project["updated_at"],
            "version_count": len(project.get("versions", [])),
            "module_counts": module_counts,
            "modules": sorted(module_counts.keys()),
        }

    def _module_summary(self, module: str, results: Dict[str, Any]) -> Dict[str, Any]:
        if module == "regression":
            stats = results.get("model_stats", {})
            return {
                "headline": f"R2 {stats.get('R-squared', 'n/a')}",
                "secondary": f"Model {results.get('inputs', {}).get('model_type', 'n/a')}",
            }
        if module == "scenario":
            base_year = results.get("base_year", {})
            return {
                "headline": f"Demand {base_year.get('total_demand_gwh', 'n/a')} GWh",
                "secondary": f"Base year {base_year.get('year', 'n/a')}",
            }
        if module == "financial":
            summary = results.get("summary", {})
            return {
                "headline": summary.get("Project NPV (USD)", "n/a"),
                "secondary": summary.get("LCOE (USD/MWh)", "n/a"),
            }
        return {"headline": "Saved", "secondary": ""}

    def _read_project(self, project_id: str, required: bool = True) -> Optional[Dict[str, Any]]:
        filepath = self.base_dir / f"{project_id}.json"
        if not filepath.exists():
            if required:
                raise FileNotFoundError(f"Project '{project_id}' not found.")
            return None
        with filepath.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_project(self, project_id: str, payload: Dict[str, Any]) -> None:
        filepath = self.base_dir / f"{project_id}.json"
        with filepath.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _slugify(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or f"project-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
