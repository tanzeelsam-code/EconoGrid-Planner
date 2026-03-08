"""
Board-style PDF report generation for saved projects.
"""

from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from config import PDF_OUTPUT_DIR


class ProjectReportGenerator:
    """Generate a concise PDF report from a saved project."""

    def __init__(self, output_dir: Path = PDF_OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.styles = self._build_styles()

    def generate(self, project: Dict[str, Any]) -> Path:
        filename = f"{project['project_id']}_board_report.pdf"
        filepath = self.output_dir / filename

        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )

        story: List[Any] = []
        story.extend(self._cover(project))
        story.extend(self._module_section(project, "regression", "Demand Forecasting"))
        story.extend(self._module_section(project, "scenario", "Scenario Planning"))
        story.extend(self._module_section(project, "financial", "Financial Screening"))

        doc.build(story)
        return filepath

    def _cover(self, project: Dict[str, Any]) -> List[Any]:
        modules = ", ".join(sorted(project.get("latest_by_module", {}).keys())) or "No modules saved"
        return [
            Paragraph("EconoGrid Planner", self.styles["ReportTitle"]),
            Paragraph("Board Report", self.styles["ReportSubtitle"]),
            Spacer(1, 8),
            Paragraph(project["project_name"], self.styles["ReportHeading"]),
            Spacer(1, 6),
            Paragraph(f"Updated: {project['updated_at']}", self.styles["ReportBody"]),
            Paragraph(f"Modules included: {modules}", self.styles["ReportBody"]),
            Spacer(1, 16),
        ]

    def _module_section(self, project: Dict[str, Any], module: str, title: str) -> List[Any]:
        version = self._latest_module(project, module)
        if version is None:
            return []

        rows = [["Field", "Value"]]
        summary_rows = self._extract_rows(module, version)
        rows.extend(summary_rows)

        table = Table(rows, colWidths=[55 * mm, 110 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D3E0")),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("LEADING", (0, 0), (-1, -1), 11),
        ]))

        return [
            Paragraph(title, self.styles["ReportSection"]),
            Paragraph(
                f"Latest version: {version['version_id']} saved {version['created_at']}",
                self.styles["ReportBodyMuted"],
            ),
            Spacer(1, 4),
            table,
            Spacer(1, 12),
        ]

    def _extract_rows(self, module: str, version: Dict[str, Any]) -> List[List[str]]:
        results = version.get("results", {})
        if module == "regression":
            stats = results.get("model_stats", {})
            validation = (results.get("validation") or {}).get("summary", {})
            return [
                ["Model", str(version.get("inputs", {}).get("model_type", "n/a"))],
                ["R-squared", str(stats.get("R-squared", "n/a"))],
                ["Adjusted R-squared", str(stats.get("Adjusted R-squared", "n/a"))],
                ["Durbin-Watson", str(stats.get("Durbin-Watson", "n/a"))],
                ["Holdout MAPE (%)", str(validation.get("MAPE (%)", "n/a"))],
                ["Holdout Bias (%)", str(validation.get("Bias (%)", "n/a"))],
            ]
        if module == "scenario":
            base = results.get("base_year", {})
            supply = results.get("supply_summary", [])
            top_supply = supply[0] if supply else {}
            return [
                ["Base year", str(base.get("year", "n/a"))],
                ["Demand (GWh)", str(base.get("total_demand_gwh", "n/a"))],
                ["Required capacity (MW)", str(base.get("required_capacity_mw", "n/a"))],
                ["Final gross generation (GWh)", str(top_supply.get("Final Gross Generation (GWh)", "n/a"))],
                ["Renewable share (%)", str(top_supply.get("Renewable Share (%)", "n/a"))],
                ["Thermal share (%)", str(top_supply.get("Thermal Share (%)", "n/a"))],
            ]
        if module == "financial":
            summary = results.get("summary", {})
            return [
                ["Project NPV", str(summary.get("Project NPV (USD)", "n/a"))],
                ["Equity NPV", str(summary.get("Equity NPV (USD)", "n/a"))],
                ["Project IRR", str(summary.get("FIRR (Project)", "n/a"))],
                ["Equity IRR", str(summary.get("Equity IRR", "n/a"))],
                ["Minimum DSCR", str(summary.get("Minimum DSCR", "n/a"))],
                ["LLCR", str(summary.get("LLCR", "n/a"))],
            ]
        return [["Status", "Saved"]]

    def _latest_module(self, project: Dict[str, Any], module: str) -> Dict[str, Any]:
        target = project.get("latest_by_module", {}).get(module)
        if not target:
            return None
        for version in reversed(project.get("versions", [])):
            if version["version_id"] == target:
                return version
        return None

    def _build_styles(self):
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0F2743"),
            spaceAfter=4,
        ))
        styles.add(ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#4A6682"),
            spaceAfter=12,
        ))
        styles.add(ParagraphStyle(
            name="ReportHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#1F4E79"),
            spaceAfter=4,
        ))
        styles.add(ParagraphStyle(
            name="ReportSection",
            parent=styles["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#16324F"),
            spaceAfter=4,
        ))
        styles.add(ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#22313F"),
            spaceAfter=2,
        ))
        styles.add(ParagraphStyle(
            name="ReportBodyMuted",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#586B7A"),
            spaceAfter=4,
        ))
        return styles
