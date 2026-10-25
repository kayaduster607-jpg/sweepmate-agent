"""Verify synthetic record contracts and truthful demonstration tools."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from agent.tools import agent_tools as tools


class RecordTests(unittest.TestCase):
    def test_all_random_demo_combinations_have_synthetic_records(self):
        records = tools.read_external_records(tools.get_abs_path(tools.agent_conf["external_data_path"]))
        self.assertEqual(sum(len(months) for months in records.values()), 120)
        for user_id in tools.user_ids:
            for month in tools.month_arr:
                self.assertIn("合成演示", records[user_id][month]["效率"])

    def test_quoted_commas_survive_csv_parsing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["user_id", "feature", "efficiency", "consumables", "comparison", "month"])
                writer.writerow(["1001", "one, two", "demo", "demo", "demo", "2025-01"])
            self.assertEqual(tools.read_external_records(path)["1001"]["2025-01"]["特征"], "one, two")

    def test_missing_csv_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "records.csv"
            path.write_text("unexpected\nvalue\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                tools.read_external_records(path)

    def test_fetch_returns_json_text_and_missing_record_returns_empty(self):
        tools.external_data.clear()
        result = tools.fetch_external_data.invoke({"user_id": "1001", "month": "2025-01"})
        self.assertIsInstance(result, str)
        self.assertIn("合成演示", json.loads(result)["特征"])
        self.assertEqual(tools.fetch_external_data.invoke({"user_id": "unknown", "month": "2025-01"}), "")

    def test_weather_tool_is_fixed_not_an_external_call(self):
        result = tools.get_weather.invoke({"city": "Demo City"})
        self.assertIn("Demo City", result)
        self.assertIn("26", result)
        self.assertIn("演示", tools.get_weather.description)
