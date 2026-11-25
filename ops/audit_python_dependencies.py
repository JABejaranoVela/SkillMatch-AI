"""Audit the exact distributions reported by pip inspect."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


FIRST_PARTY = "skillmatch-ai-backend"


def normalized_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_requirements(inventory):
    pinned = {}
    unverified = []
    for item in inventory["installed"]:
        metadata = item["metadata"]
        name, version = metadata["name"], metadata["version"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise ValueError("Invalid distribution name")
        if not re.fullmatch(r"[0-9][A-Za-z0-9._+!-]*", version):
            raise ValueError("Invalid distribution version")
        name = normalized_name(name)
        if name == FIRST_PARTY:
            continue
        if name in pinned:
            raise ValueError("Duplicate installed distribution")
        pinned[name] = version
        if "direct_url" in item:
            unverified.append(name)
    if not pinned:
        raise ValueError("No third-party distributions in inventory")
    return pinned, unverified


def audit_inventory(inventory, output_dir):
    installed, unverified = installed_requirements(inventory)
    requirements = output_dir / "requirements.txt"
    requirements.write_text(
        "".join(f"{name}=={version}\n" for name, version in sorted(installed.items())),
        encoding="utf-8",
    )
    if unverified:
        # A direct URL can identify a different build from the index version.
        index_requirements = output_dir / "index-requirements.txt"
        index_requirements.write_text(
            "".join(
                f"{name}=={version}\n"
                for name, version in sorted(installed.items())
                if name not in unverified
            ),
            encoding="utf-8",
        )
        requirements = index_requirements
    expected = set(installed.items()) - {(name, installed[name]) for name in unverified}
    if not expected:
        raise ValueError("No index-backed distributions to audit")

    report = output_dir / "audit.json"
    report.unlink(missing_ok=True)
    result = subprocess.run(
        [
            sys.executable, "-m", "pip_audit", "--no-deps", "--disable-pip",
            "--format", "json", "--output", str(report), "--progress-spinner", "off",
            "--timeout", "20", "-r", str(requirements),
        ],
        check=False,
    )
    if result.returncode not in (0, 1):
        raise ValueError(f"pip-audit failed with exit code {result.returncode}")

    verified = set()
    findings = set()
    skipped = list(unverified)
    for item in json.loads(report.read_text(encoding="utf-8"))["dependencies"]:
        name = normalized_name(item["name"])
        if "skip_reason" in item:
            skipped.append(name)
            continue
        verified.add((name, item["version"]))
        findings.update((name, vuln["id"]) for vuln in item["vulns"])
    complete = verified == expected and not skipped and result.returncode == bool(findings)
    status = "incomplete" if not complete else "findings" if findings else "clean"
    return {
        "status": status,
        "installed": len(installed),
        "audited": len(verified & expected),
        "findings": len(findings),
        "unverified_distributions": sorted(set(skipped) | {name for name, _ in expected - verified}),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=("ci-dev", "production", "dev-ner"), required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--image-id")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    try:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        result = audit_inventory(inventory, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # Malformed or missing data cannot establish a clean audit.
        result = {"status": "incomplete", "error": type(exc).__name__}
    result.update(profile=args.profile, source_sha=args.source_sha, image_id=args.image_id)
    (args.output_dir / "status.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(f"{args.profile}: {result['status']}")
    return int(result["status"] == "incomplete")


if __name__ == "__main__":
    sys.exit(main())
