"""Couverture des plans, de l'union des segments et des échecs sans export."""

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from frco.cli.app import app
from frco.services.company_service import CompanyService
from frco.services.prospect_list_service import ProspectFilters, ProspectListError, ProspectListService
from frco.services.segmented_research import ResearchSegment, collect_segments, load_segments
from test_prospect_list import FakeClient, company_record


def write_plan(directory: str, entries: list[dict]) -> Path:
    path = Path(directory) / "plan.json"
    path.write_text(json.dumps({"version": 1, "segments": entries}), encoding="utf-8")
    return path


class SegmentedResearchTests(unittest.TestCase):
    def test_plan_inherits_all_filters_and_narrows_naf(self) -> None:
        base = ProspectFilters(
            naf="62.02", region="11", department="75", employees_min=20,
            revenue_min=1000000, multi_site_only=True, active_only=True,
        )
        with tempfile.TemporaryDirectory() as directory:
            plan = write_plan(directory, [{"id": "paris15-a", "city": "75115", "naf": "62.02A"}])
            segments = load_segments(plan, base)
        self.assertEqual(segments[0].filters, replace(base, city="75115", naf="62.02A"))

    def test_plan_cannot_change_business_criteria_or_widen_existing_filters(self) -> None:
        base = ProspectFilters(naf="62.02", department="75", revenue_min=1000000)
        invalid = [
            [{"id": "x", "revenue_min": 0}],
            [{"id": "x", "department": "92"}],
            [{"id": "x", "naf": "69.20"}],
            [{"id": "x", "city": "Paris"}],
            [{"id": "x", "city": None}],
            [{"id": "x"}, {"id": "x", "city": "75115"}],
            [{"id": "x"}, {"id": "y"}],
            [],
        ]
        with tempfile.TemporaryDirectory() as directory:
            for entries in invalid:
                with self.subTest(entries=entries):
                    with self.assertRaises(ProspectListError):
                        load_segments(write_plan(directory, entries), base)

    def test_malformed_plan_is_rejected_before_api(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "broken.json"
            plan.write_text("{", encoding="utf-8")
            with patch("frco.cli.prospect_list.ApiGouvClient") as client:
                result = CliRunner().invoke(app, ["list", "62.02", "--segments", str(plan)])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Plan de segments illisible", result.stderr)
        client.assert_not_called()

    def test_all_segments_are_validated_before_any_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = write_plan(directory, [
                {"id": "first", "city": "75115"},
                {"id": "invalid", "naf": "69.20"},
            ])
            with patch("frco.cli.prospect_list.ApiGouvClient") as client:
                result = CliRunner().invoke(app, ["list", "62.02", "--segments", str(plan)])
        self.assertEqual(result.exit_code, 1)
        client.assert_not_called()

    def test_merge_deduplicates_siren_and_retains_latest_whole_record(self) -> None:
        service = ProspectListService(FakeClient([]))
        first = CompanyService(FakeClient([])).from_result(company_record(1, finances=None))
        latest = replace(first, name="NOUVEAU NOM", metadata=replace(first.metadata, retrieved_at="2099-01-01T00:00:00Z"))
        second = CompanyService(FakeClient([])).from_result(company_record(2))
        segments = [
            ResearchSegment("a", ProspectFilters(naf="62.02A", city="75101")),
            ResearchSegment("b", ProspectFilters(naf="62.02A", city="75102")),
        ]
        with patch.object(service, "build", side_effect=[[first], [latest, second]]):
            result = collect_segments(service, segments)
        self.assertEqual(result.segment_count, 2)
        self.assertEqual(result.occurrence_count, 3)
        self.assertEqual(result.companies, [latest, second])
        self.assertEqual(result.companies[0].revenue_history, [])

    def test_union_can_exceed_api_cap_when_each_segment_is_below_it(self) -> None:
        class RoutedClient:
            def __init__(self):
                self.clients = {
                    "62.02A": FakeClient([company_record(i) for i in range(5001)]),
                    "62.02B": FakeClient([
                        company_record(i, activite_principale="62.02B") for i in range(5001, 10002)
                    ]),
                }

            def search_companies(self, filters, *, page, per_page=25):
                return self.clients[filters["activite_principale"]].search_companies(filters, page=page, per_page=per_page)

        client = RoutedClient()
        segments = [ResearchSegment(code, ProspectFilters(naf=code)) for code in ("62.02A", "62.02B")]
        result = collect_segments(ProspectListService(client), segments)
        self.assertEqual(len(result.companies), 10002)
        self.assertEqual(result.occurrence_count, 10002)
        self.assertEqual([len(c.calls) for c in client.clients.values()], [201, 201])

    def test_segmented_cli_writes_one_union_and_keeps_unknown_revenue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = write_plan(directory, [{"id": "p1", "city": "75101"}, {"id": "p2", "city": "75102"}])
            output = Path(directory) / "union.json"
            client = FakeClient([company_record(1, finances=None)])
            with patch("frco.cli.prospect_list.ApiGouvClient", return_value=client):
                result = CliRunner().invoke(app, ["list", "62.02A", "--department", "75", "--segments", str(plan), "-o", str(output)])
            self.assertEqual(result.exit_code, 0, result.stderr)
            records = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(records, json.loads(result.stdout))
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["revenue_history"], [])
            self.assertEqual([call[0]["code_commune"] for call in client.calls], ["75101", "75102"])
            self.assertTrue(all(call[0]["departement"] == "75" for call in client.calls))
            self.assertIn("occurrences : 2", result.stderr)
            self.assertIn("Couverture limitée aux segments fournis", result.stderr)

    def test_failed_leaf_preserves_output_and_identifies_segment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = write_plan(directory, [{"id": "ok", "city": "75101"}, {"id": "too-wide", "city": "75102"}])
            output = Path(directory) / "union.json"
            output.write_text("[]", encoding="utf-8")
            company = CompanyService(FakeClient([])).from_result(company_record(1))
            with patch("frco.services.segmented_research.ProspectListService.build", side_effect=[[company], ProspectListError("10 000 résultats")]):
                result = CliRunner().invoke(app, ["list", "62.02A", "--segments", str(plan), "-o", str(output)])
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("Segment too-wide", result.stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), "[]")

    def test_output_cannot_replace_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = write_plan(directory, [{"id": "x", "city": "75101"}])
            original = plan.read_text(encoding="utf-8")
            with patch("frco.cli.prospect_list.ApiGouvClient") as client:
                result = CliRunner().invoke(app, ["list", "62.02A", "--segments", str(plan), "-o", str(plan)])
            self.assertEqual(result.exit_code, 1)
            self.assertEqual(plan.read_text(encoding="utf-8"), original)
            client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
