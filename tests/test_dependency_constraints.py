from __future__ import annotations

import unittest
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def requirements(path: Path) -> dict[str, Requirement]:
    parsed: dict[str, Requirement] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        requirement = Requirement(value)
        key = canonicalize_name(requirement.name)
        if key in parsed:
            raise AssertionError(f"Duplicate pinned requirement: {key}")
        parsed[key] = requirement
    return parsed


class DependencyConstraintsTests(unittest.TestCase):
    def test_locked_runtime_versions_satisfy_declared_constraints(self) -> None:
        self._check("requirements.txt", "requirements.lock.txt")

    def test_locked_build_versions_satisfy_declared_constraints(self) -> None:
        self._check("requirements-build.txt", "requirements-build.lock.txt")

    def _check(self, declared_name: str, locked_name: str) -> None:
        declared = requirements(ROOT / declared_name)
        locked = requirements(ROOT / locked_name)
        self.assertTrue(declared)
        for name, expected in declared.items():
            with self.subTest(package=name, declared=declared_name):
                self.assertIn(name, locked)
                pinned = locked[name].specifier
                self.assertEqual(
                    len(list(pinned)),
                    1,
                    f"{name} is not pinned to exactly one version in {locked_name}",
                )
                only = next(iter(pinned))
                self.assertEqual(only.operator, "==")
                self.assertTrue(
                    expected.specifier.contains(only.version, prereleases=True),
                    f"{name}=={only.version} conflicts with {declared_name}: "
                    f"{expected.specifier}",
                )


if __name__ == "__main__":
    unittest.main()
