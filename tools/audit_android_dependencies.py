from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
_COORDINATE_RE = re.compile(r'"([A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:([A-Za-z0-9_.+\-]+))"')
_PLUGIN_RE = re.compile(r'id\s+"([^"]+)"\s+version\s+"([^"]+)"')
_PLUGIN_COORDINATES = {
    "com.android.application": "com.android.tools.build:gradle",
    "com.google.protobuf": "com.google.protobuf:protobuf-gradle-plugin",
}


def collect_dependencies(root: Path) -> list[tuple[str, str]]:
    dependencies: set[tuple[str, str]] = set()

    android_gradle = (root / "android" / "build.gradle").read_text(encoding="utf-8")
    for match in _COORDINATE_RE.finditer(android_gradle):
        coordinate = match.group(1)
        group, artifact, version = coordinate.split(":", 2)
        if "$" not in version and version:
            dependencies.add((f"{group}:{artifact}", version))

    root_gradle = (root / "build.gradle").read_text(encoding="utf-8")
    for plugin_id, version in _PLUGIN_RE.findall(root_gradle):
        coordinate = _PLUGIN_COORDINATES.get(plugin_id)
        if coordinate:
            dependencies.add((coordinate, version))

    return sorted(dependencies)


def query_osv(dependencies: list[tuple[str, str]], *, attempts: int = 3) -> dict[str, object]:
    payload = {
        "queries": [
            {
                "package": {"ecosystem": "Maven", "name": name},
                "version": version,
            }
            for name, version in dependencies
        ]
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            OSV_BATCH_URL,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "SindromeChatOverlay-CI/1"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    raise RuntimeError(f"OSV returned HTTP {response.status}")
                decoded = json.loads(response.read(4 * 1024 * 1024).decode("utf-8"))
                if not isinstance(decoded, dict):
                    raise RuntimeError("OSV returned an unexpected response")
                return decoded
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)

    raise RuntimeError(f"Unable to query OSV after {attempts} attempts: {last_error}")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    dependencies = collect_dependencies(root)
    if not dependencies:
        print("No Android Maven dependencies found to audit.", file=sys.stderr)
        return 2

    print(f"Auditing {len(dependencies)} Android/Gradle dependencies against OSV...")
    payload = query_osv(dependencies)
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(dependencies):
        print("OSV response did not match the dependency request.", file=sys.stderr)
        return 2

    vulnerable: list[tuple[str, str, list[str]]] = []
    for (name, version), result in zip(dependencies, results, strict=True):
        vulns = result.get("vulns", []) if isinstance(result, dict) else []
        ids = sorted(
            {
                str(vuln.get("id"))
                for vuln in vulns
                if isinstance(vuln, dict) and vuln.get("id")
            }
        )
        if ids:
            vulnerable.append((name, version, ids))
        else:
            print(f"  OK  {name}:{version}")

    if vulnerable:
        print("\nKnown vulnerabilities were found:", file=sys.stderr)
        for name, version, ids in vulnerable:
            print(f"  {name}:{version} -> {', '.join(ids)}", file=sys.stderr)
        return 1

    print("Android/Gradle OSV audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
