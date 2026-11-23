"""Release provenance tests using fake GitHub and Git commands."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify-release.sh"
ACTIONS_BOT = "github-actions[bot]"
APP_BOT = "example-release[bot]"
SHA = "a" * 40


@unittest.skipUnless(shutil.which("bash") and shutil.which("jq"), "requires Bash and jq")
class VerifyReleaseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.output = self.root / "outputs"
        self.stub("gh", """
import json, os, sys
repo = os.environ["GITHUB_REPOSITORY"]
if "/releases/tags/" in sys.argv[-1]:
    print(json.dumps({"tag_name": "v0.1.0", "draft": False, "prerelease": False,
                      "author": {"login": os.environ["RELEASE_AUTHOR"]}}))
else:
    print(json.dumps([[{
        "base": {"ref": "main", "repo": {"full_name": repo}},
        "head": {"ref": "release-please--branches--main", "repo": {"full_name": repo}},
        "user": {"login": os.environ["PR_AUTHOR"]},
        "merged_at": "2026-01-01T00:00:00Z",
        "merge_commit_sha": os.environ["GITHUB_SHA"],
        "labels": [{"name": "autorelease: tagged"}],
    }]]))
""")
        self.stub("git", """
import os, sys
args = sys.argv[1:]
if args[0] == "rev-parse":
    print(os.environ["GITHUB_SHA"])
elif args[0] == "merge-base":
    sys.exit(os.environ["OUTSIDE_MAIN"] == "true")
elif args[-1].endswith(":version.txt"):
    print("0.1.0")
else:
    print('{".": "0.1.0"}')
""")

    def stub(self, name, code):
        path = self.root / name
        path.write_text(f"#!{sys.executable}\n{code}")
        path.chmod(0o755)

    def verify(self, release_author, pr_author, app_bot="", outside_main="false"):
        return subprocess.run(
            ["bash", str(SCRIPT)],
            env=os.environ | {
                "PATH": f"{self.root}:{os.environ['PATH']}",
                "GITHUB_REPOSITORY": "example/repo",
                "GITHUB_SHA": SHA,
                "GITHUB_OUTPUT": str(self.output),
                "RELEASE_TAG": "v0.1.0",
                "RELEASE_PLEASE_APP_BOT": app_bot,
                "RELEASE_AUTHOR": release_author,
                "PR_AUTHOR": pr_author,
                "OUTSIDE_MAIN": outside_main,
            },
            text=True, capture_output=True, timeout=5,
        )

    def assert_verified(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.output.read_text(), f"tag=v0.1.0\nsha={SHA}\n")

    def assert_rejected(self, result, error):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(error, result.stderr)
        self.assertFalse(self.output.exists())

    def test_builtin_identity_still_works_with_optional_app_configured(self):
        self.assert_verified(self.verify(ACTIONS_BOT, ACTIONS_BOT, APP_BOT))

    def test_explicit_github_app_is_accepted_for_release_and_pr(self):
        self.assert_verified(self.verify(APP_BOT, APP_BOT, APP_BOT))

    def test_unconfigured_bot_or_human_cannot_publish(self):
        for author in (APP_BOT, "example-release"):
            with self.subTest(author=author):
                self.assert_rejected(self.verify(author, author), "authorized bot")

    def test_human_login_is_rejected_as_app_configuration(self):
        self.assert_rejected(self.verify("person", "person", "person"), "invalid Release Please App")

    def test_pr_author_must_match_the_release_author(self):
        for author in (ACTIONS_BOT, "other[bot]"):
            with self.subTest(author=author):
                self.assert_rejected(self.verify(APP_BOT, author, APP_BOT), "no matching merged")

    def test_authorized_identity_cannot_release_a_commit_outside_main(self):
        self.assert_rejected(self.verify(APP_BOT, APP_BOT, APP_BOT, "true"), "outside main")
