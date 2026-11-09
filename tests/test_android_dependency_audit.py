from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.audit_android_dependencies import (
    collect_dependencies,
    collect_resolved_dependencies,
    main,
)


class GradleResolvedAuditTests(unittest.TestCase):
    def test_parses_and_deduplicates_transitive_maven_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.txt"
            path.write_text(
                "com.squareup.okio:okio:3.9.0\n"
                "com.google.guava:guava:33.4.8-android\n"
                "com.squareup.okio:okio:3.9.0\n"
                "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                collect_resolved_dependencies(path),
                [
                    ("com.google.guava:guava", "33.4.8-android"),
                    ("com.squareup.okio:okio", "3.9.0"),
                ],
            )

    def test_empty_and_malformed_reports_are_rejected(self) -> None:
        invalid = ("", "project :android", "com.example:lib", "com.example:lib:+", "com.example:lib:1.0\nnot valid")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.txt"
            for content in invalid:
                with self.subTest(content=content):
                    path.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        collect_resolved_dependencies(path)

    def test_missing_resolved_file_fails_closed_before_osv_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "absent.txt"
            with patch("tools.audit_android_dependencies.query_osv") as query:
                self.assertEqual(main(["--resolved-file", str(path)]), 2)
                query.assert_not_called()

    def test_osv_receives_both_declared_and_transitive_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.txt"
            path.write_text("com.example:transitive:1.2.3\n", encoding="utf-8")

            def fake_query(requested):
                self.assertIn(("com.example:transitive", "1.2.3"), requested)
                # Compare against the project's declared OkHttp coordinate;
                # a hard-coded old version would break on every safe upgrade.
                root = Path(__file__).resolve().parents[1]
                declared = dict(collect_dependencies(root))
                self.assertIn("com.squareup.okhttp3:okhttp", declared)
                self.assertIn(
                    ("com.squareup.okhttp3:okhttp", declared["com.squareup.okhttp3:okhttp"]),
                    requested,
                )
                return {"results": [{} for _ in requested]}

            with patch("tools.audit_android_dependencies.query_osv", side_effect=fake_query):
                self.assertEqual(main(["--resolved-file", str(path)]), 0)

    def test_osv_alert_in_resolved_transitive_dependency_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.txt"
            path.write_text("com.example:transitive:1.2.3\n", encoding="utf-8")

            def fake_query(requested):
                return {
                    "results": [
                        {"vulns": [{"id": "GHSA-example-test"}]}
                        if pair == ("com.example:transitive", "1.2.3") else {}
                        for pair in requested
                    ]
                }

            with patch("tools.audit_android_dependencies.query_osv", side_effect=fake_query):
                self.assertEqual(main(["--resolved-file", str(path)]), 1)


if __name__ == "__main__":
    unittest.main()
