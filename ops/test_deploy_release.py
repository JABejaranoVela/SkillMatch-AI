"""Deploy-release regression tests. Run with Python and Bash on Linux."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy-release.sh"
BACKEND = "ghcr.io/example/skillmatch-ai-backend"
FRONTEND = "ghcr.io/example/skillmatch-ai-frontend"


def digest(letter):
    return "sha256:" + letter * 64


LEGACY = (digest("1"), digest("2"))
FIRST = (digest("3"), digest("4"))
SECOND = (digest("5"), digest("6"))


@unittest.skipUnless(shutil.which("bash") and shutil.which("flock"), "requires Bash and flock")
class DeployReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.app = self.root / "app"
        self.state = self.root / "ledger"
        self.runtime = self.root / "runtime"
        self.deployer = self.app / "scripts" / "deploy-production.sh"
        self.deployer.parent.mkdir(parents=True)
        self.state.mkdir()
        self.source = SCRIPT.read_text().replace(
            "app_dir=/srv/apps/skillmatch-ai", f"app_dir={shlex.quote(str(self.app))}"
        ).replace(
            "state_dir=/srv/backups/skillmatch-ai/postgres/.release-deployments",
            f"state_dir={shlex.quote(str(self.state))}",
        )
        self.assertNotIn("/srv/", self.source)
        self.env = os.environ | {"PATH": f"{self.root}:{os.environ['PATH']}", "FIXTURE": str(self.root)}
        self.set_running(*LEGACY)
        self.stub("git", r"""
import os, pathlib, re, sys
root = pathlib.Path(os.environ["FIXTURE"])
command, *args = sys.argv[1:]
if command == "rev-parse":
    if args == ["--verify", "HEAD"]:
        print((root / "head").read_text())
    else:
        patch = re.search(r"v0\.1\.(\d+)", args[-1])[1]
        print(chr(ord("a") + int(patch)) * 40)
elif command == "merge-base":
    sys.exit(args[-1] != "refs/remotes/origin/main" and args[-2] > args[-1])
elif command == "checkout":
    assert args[0] == "--detach"
    (root / "head").write_text(args[-1])
elif command == "status":
    assert args == ["--porcelain=v1", "--untracked-files=all"]
    status = root / "checkout-status"
    if status.exists():
        print(status.read_text(), end="")
elif command != "diff":
    sys.exit(2)
""")
        self.stub("sudo", """
import hashlib, json, os, pathlib, sys
root = pathlib.Path(os.environ["FIXTURE"])
running = json.loads((root / "runtime").read_text())
containers = dict(zip(("backend", "email-worker", "frontend"), "abc"))
tag_file = root / "local-tags"
tags = json.loads(tag_file.read_text()) if tag_file.exists() else {}
def id_of(digest):
    return "sha256:" + hashlib.sha256(digest.encode()).hexdigest()
args = sys.argv[3:]
if args[0] == "compose":
    assert args[-5:-1] == ["ps", "--status", "running", "--quiet"]
    if running.get(args[-1]):
        print(containers[args[-1]] * 64)
elif args[0] == "inspect":
    service = next(name for name, cid in containers.items() if args[-1] == cid * 64)
    print(id_of(running[service]))
elif args[:2] == ["image", "inspect"]:
    target = args[-1]
    if target.startswith("skillmatch-retained/"):
        print(tags[target])
    elif target.startswith("ghcr.io/"):
        repo, ref_digest = target.split("@")
        if os.getenv("MOCK_UNRESOLVABLE") == repo or ref_digest not in running.values():
            sys.exit(1)
        print(id_of(ref_digest))
    else:
        service = next(name for name, digest in running.items() if digest and id_of(digest) == target)
        if service != os.getenv("MOCK_NO_DIGEST"):
            print("ghcr.io/example/skillmatch-ai-" + service + "@" + running[service])
elif args[:2] == ["image", "ls"]:
    filter_tag = args[-1].removeprefix("reference=")
    if filter_tag in tags:
        print(filter_tag)
elif args[:2] == ["image", "tag"]:
    assert args[-2].startswith("sha256:")
    tags[args[-1]] = args[-2]
    tag_file.write_text(json.dumps(tags))
else:
    sys.exit(2)
""")
        self.deployer.write_text("""#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >> "$FIXTURE/calls"
cat > "$FIXTURE/child-stdin"
printf 'BACKEND_IMAGE=ghcr.io/example/skillmatch-ai-backend@%s\nFRONTEND_IMAGE=ghcr.io/example/skillmatch-ai-frontend@%s\n' "$3" "$4" > .env.deploy
if [[ "${MOCK_OUTCOME:-}" == failure ]]; then
  exit 17
fi
if [[ "${MOCK_OUTCOME:-}" != unchanged ]]; then
  printf '{"backend":"%s","email-worker":"%s","frontend":"%s"}\n' "$3" "$3" "$4" > "$FIXTURE/runtime"
fi
""")

    def stub(self, name, code):
        path = self.root / name
        path.write_text(f"#!{sys.executable}\n{code}")
        path.chmod(0o755)

    def set_running(self, backend, frontend, worker="same"):
        self.runtime.write_text(json.dumps({
            "backend": backend, "email-worker": backend if worker == "same" else worker,
            "frontend": frontend,
        }))

    def arguments(self, patch):
        images = FIRST if patch == 0 else SECOND
        return ["bash", "-s", "--", f"v0.1.{patch}", chr(ord("a") + patch) * 40,
                "example", str(self.root), *images]

    def deploy(self, patch=0, outcome="", no_digest="", unresolvable=""):
        return subprocess.run(
            self.arguments(patch), cwd=self.app,
            env=self.env | {"MOCK_OUTCOME": outcome, "MOCK_NO_DIGEST": no_digest,
                            "MOCK_UNRESOLVABLE": unresolvable},
            input=self.source, text=True, capture_output=True, timeout=10,
        )

    def calls(self):
        path = self.root / "calls"
        return path.read_text().count("called\n") if path.exists() else 0

    def assert_completed(self, result, patch=0):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.state / f"v0.1.{patch}.deployed").is_file())
        self.assertFalse((self.state / "pending").exists())

    def test_streamed_script_finishes_when_child_reads_until_eof(self):
        prefix, ending = self.source.rsplit('\nmv -T -- "$state_dir/pending" "$receipt"', 1)
        with subprocess.Popen(self.arguments(0), cwd=self.app, env=self.env, text=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as child:
            try:
                child.stdin.write(prefix + "\n")
                child.stdin.flush()
                deadline = time.monotonic() + 5
                while not (self.root / "child-stdin").exists() and child.poll() is None:
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.01)
                # Deliver the final instruction only after the child starts reading.
                child.stdin.write('mv -T -- "$state_dir/pending" "$receipt"' + ending)
                _, stderr = child.communicate(timeout=5)
            finally:
                if child.poll() is None:
                    child.kill()
        self.assertEqual(child.returncode, 0, stderr)
        self.assertEqual((self.root / "child-stdin").read_text(), "")
        self.assertTrue((self.state / "v0.1.0.deployed").exists())
        self.assertFalse((self.state / "pending").exists())

    def test_current_release_is_noop_only_when_running_images_match(self):
        self.assert_completed(self.deploy())
        result = self.deploy()
        self.assert_completed(result)
        self.assertIn("already deployed", result.stdout)
        self.assertEqual((self.root / "head").read_text(), "a" * 40)
        self.set_running(*LEGACY)
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("operator reconciliation required", result.stderr)
        self.assertEqual(self.calls(), 1)

    def test_checkout_at_a_different_commit_blocks_noop(self):
        self.assert_completed(self.deploy())
        head = self.root / "head"
        head.write_text("b" * 40)
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkout SHA does not match the deployed receipt", result.stderr)
        self.assertNotIn("already deployed", result.stdout)
        self.assertEqual(head.read_text(), "b" * 40)
        self.assertEqual(self.calls(), 1)

    def test_unexpected_checkout_changes_block_noop(self):
        self.assert_completed(self.deploy())
        checkout = self.root / "checkout-status"
        for status in (" M compose.yml", "M  compose.yml", "?? unexpected.txt"):
            with self.subTest(status=status):
                checkout.write_text(status + "\n")
                result = self.deploy()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("checkout has unexpected changes", result.stderr)
                self.assertNotIn("already deployed", result.stdout)
                self.assertEqual(checkout.read_text(), status + "\n")
        self.assertEqual(self.calls(), 1)

    def test_older_release_is_rejected_after_newer_completion(self):
        self.assert_completed(self.deploy())
        self.assert_completed(self.deploy(1), 1)
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("older than", result.stderr)
        self.assertEqual(self.calls(), 2)

    def test_saved_config_from_failed_release_blocks_noop_for_current_release(self):
        self.assert_completed(self.deploy())
        config = self.app / ".env.deploy"
        original = config.read_bytes()
        self.assertEqual(self.deploy(1, "failure").returncode, 17)
        (self.state / "pending").rename(self.state / "reconciled")
        partial = config.read_bytes()
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(".env.deploy does not match the recorded digests", result.stderr)
        self.assertEqual(config.read_bytes(), partial)
        self.assertEqual(self.calls(), 2)
        config.write_bytes(original)
        # Restoring Compose without restoring Git must still refuse the no-op.
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("checkout SHA does not match the deployed receipt", result.stderr)
        (self.root / "head").write_text("a" * 40)
        self.assert_completed(self.deploy())
        self.assertEqual(self.calls(), 2)

    def test_pending_still_blocks_with_matching_checkout_and_running_images(self):
        self.assert_completed(self.deploy())
        original = (self.app / ".env.deploy").read_bytes()
        self.assertEqual(self.deploy(1, "failure").returncode, 17)
        (self.app / ".env.deploy").write_bytes(original)
        (self.root / "head").write_text("a" * 40)
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("previous attempt requires operator reconciliation", result.stderr)
        self.assertTrue((self.state / "pending").exists())
        self.assertEqual(self.calls(), 2)

    def test_retention_keeps_legacy_active_and_previous_release_images(self):
        self.assert_completed(self.deploy())
        self.assert_completed(self.deploy(1), 1)
        tags = json.loads((self.root / "local-tags").read_text())
        expected_tags = {
            f"skillmatch-retained/{service}:sha256-{value.split(':')[1]}":
                f"sha256:{sha256(value.encode()).hexdigest()}"
            for pair in (LEGACY, FIRST, SECOND)
            for service, value in zip(("backend", "frontend"), pair)
        }
        self.assertEqual(tags, expected_tags)
        self.assertNotIn("image prune", (SCRIPT.parent / "deploy-production.sh").read_text())

    def test_unresolvable_rollback_image_blocks_before_deploy(self):
        result = self.deploy(unresolvable=BACKEND)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not resolve the backend recovery digest locally", result.stderr)
        self.assertEqual(self.calls(), 0)
        self.assertFalse((self.state / "pending").exists())

    def test_conflicting_retention_tag_is_rejected_without_overwrite(self):
        path = self.root / "local-tags"
        tags = {"skillmatch-retained/backend:sha256-" + LEGACY[0].split(":")[1]: digest("f")}
        path.write_text(json.dumps(tags))
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("retention tag has the wrong image ID", result.stderr)
        self.assertEqual(json.loads(path.read_text()), tags)
        self.assertEqual(self.calls(), 0)

    def test_old_and_repeated_requests_fail_while_newer_deploy_is_pending(self):
        self.assert_completed(self.deploy())
        self.assertEqual(self.deploy(1, "failure").returncode, 17)
        for patch in (0, 1):
            with self.subTest(patch=patch):
                result = self.deploy(patch)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("previous attempt requires operator reconciliation", result.stderr)
        self.assertEqual(self.calls(), 2)

    def test_first_failed_release_preserves_live_snapshot_after_retry(self):
        self.assertEqual(self.deploy(outcome="failure").returncode, 17)
        snapshot = self.state / "v0.1.0.previous-env"
        original = f"BACKEND_IMAGE={BACKEND}@{LEGACY[0]}\nFRONTEND_IMAGE={FRONTEND}@{LEGACY[1]}\n"
        self.assertEqual(snapshot.read_text(), original)
        self.assertIn(FIRST[0], (self.app / ".env.deploy").read_text())
        self.assertEqual((self.state / "pending").read_text().split(),
                         ["v0.1.0", "a" * 40, *FIRST])
        # Simulate operator reconciliation of the attempt. The old images are still running.
        (self.state / "pending").rename(self.state / "reconciled")
        self.assert_completed(self.deploy())
        self.assertEqual(snapshot.read_text(), original)
        self.assertEqual(self.calls(), 2)

    def test_retry_rejects_partial_rollout_without_overwriting_snapshot(self):
        self.assertEqual(self.deploy(outcome="failure").returncode, 17)
        snapshot = self.state / "v0.1.0.previous-env"
        original = snapshot.read_bytes()
        (self.state / "pending").rename(self.state / "reconciled")
        self.set_running(FIRST[0], LEGACY[1])
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("operator reconciliation required", result.stderr)
        self.assertEqual(snapshot.read_bytes(), original)
        self.assertEqual(self.calls(), 1)

    def test_unknown_live_state_blocks_initial_deploy(self):
        self.set_running(*LEGACY, worker=None)
        result = self.deploy()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected one running email-worker", result.stderr)
        self.assertFalse((self.state / "pending").exists())
        self.assertEqual(self.calls(), 0)

    def test_child_success_without_expected_live_images_keeps_pending(self):
        result = self.deploy(outcome="unchanged")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("operator reconciliation required", result.stderr)
        self.assertTrue((self.state / "pending").is_file())
        self.assertFalse((self.state / "v0.1.0.deployed").exists())

    def test_live_image_without_registry_digest_blocks_snapshot(self):
        result = self.deploy(no_digest="backend")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no registry digest", result.stderr)
        self.assertFalse((self.state / "v0.1.0.previous-env").exists())
        self.assertFalse((self.state / "pending").exists())
        self.assertEqual(self.calls(), 0)

    def test_concurrent_repeats_execute_the_child_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.deploy, [0, 0]))
        for result in results:
            self.assert_completed(result)
        self.assertEqual(self.calls(), 1)


if __name__ == "__main__":
    unittest.main()
