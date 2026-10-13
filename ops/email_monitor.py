"""VPS-only email monitor. Python standard library; no credentials in arguments or logs."""

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib import parse, request

APP_DIR = Path("/srv/apps/skillmatch-ai")
CONFIG = Path("/etc/skillmatch-ai/email-monitor.env")
STATE = Path("/srv/data/skillmatch-ai/tmp/email-monitor-state.json")


def read_config(path: Path) -> tuple[str, str]:
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("config_permissions")
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or name not in {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"}:
            raise ValueError("config_format")
        values[name] = value.strip()
    token = values.get("TELEGRAM_BOT_TOKEN", "")
    chat = values.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat or any(char in token for char in "/?&#"):
        raise ValueError("config_missing")
    return token, chat


def compose_args() -> list[str]:
    args = ["sudo", "-n", "docker", "compose", "--env-file", ".env.prod"]
    if (APP_DIR / ".env.deploy").is_file():
        args.extend(["--env-file", ".env.deploy"])
    return args + ["-f", "docker-compose.prod.yml", "-f", "docker-compose.prod.override.yml"]


def command(args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            args, cwd=APP_DIR, capture_output=True, text=True, timeout=45, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def diagnostic(check: str) -> dict[str, object] | None:
    output = command(compose_args() + [
        "exec", "-T", "backend", "python", "-m", "app.commands.email_diagnostics", check
    ])
    if output is None:
        return None
    try:
        result = json.loads(output)
        return result if isinstance(result, dict) else None
    except ValueError:
        return None


def worker_running() -> bool:
    output = command(compose_args() + ["ps", "--status", "running", "-q", "email-worker"])
    return bool(output)


def send_telegram(token: str, chat: str, message: str) -> bool:
    data = parse.urlencode({"chat_id": chat, "text": message, "disable_notification": "false"})
    req = request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data.encode("utf-8"),
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as response:
            return response.status == 200 and json.load(response).get("ok") is True
    except (OSError, ValueError, AttributeError):
        return False


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"active": {}, "seen_failed_ids": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("active"), dict) or not isinstance(
        data.get("seen_failed_ids"), list
    ):
        raise ValueError("state_format")
    return data


def save_state(path: Path, state: dict[str, object]) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=".email-monitor-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def update_issue(
    state: dict[str, object], key: str, broken: bool, label: str,
    send, save,
) -> bool:
    active = state["active"]
    was_broken = bool(active.get(key))
    if broken == was_broken:
        return True
    message = f"SkillMatch AI: {'ALERTA' if broken else 'RECUPERADO'}: {label}"
    if not send(message):
        return False
    active[key] = broken
    save()
    return True


def run_check(mode: str, state: dict[str, object], send, save) -> bool:
    success = True

    def issue(key: str, broken: bool, label: str) -> None:
        nonlocal success
        success = update_issue(state, key, broken, label, send, save) and success

    if mode == "api":
        result = diagnostic("api")
        issue("api", result is None or result.get("ok") is not True,
              "API de Brevo no responde correctamente")
        return success

    issue("worker", not worker_running(), "email-worker detenido")
    result = diagnostic("outbox")
    if result is None or result.get("ok") is not True:
        issue("query", True, "consulta de email_outbox imposible")
        return success
    try:
        failed_ids = {int(item) for item in result["failed_ids"]}
        overdue = int(result["overdue_count"])
        abandoned = int(result["abandoned_count"])
        if min(overdue, abandoned) < 0:
            raise ValueError("negative_count")
    except (KeyError, TypeError, ValueError):
        issue("query", True, "consulta de email_outbox imposible")
        return False
    issue("query", False, "consulta de email_outbox imposible")
    seen = {int(item) for item in state["seen_failed_ids"]}
    new_failures = failed_ids - seen
    if new_failures:
        if send(f"SkillMatch AI: ALERTA: {len(new_failures)} nuevo(s) correo(s) failed"):
            state["seen_failed_ids"] = sorted(seen | new_failures)
            save()
        else:
            success = False
    # Retain only rows still present; cleanup may remove old failed rows.
    retained = sorted(set(state["seen_failed_ids"]) & failed_ids)
    if retained != state["seen_failed_ids"]:
        state["seen_failed_ids"] = retained
        save()
    issue("overdue", overdue > 0, "correo pendiente con mas de 10 min de retraso")
    issue("abandoned", abandoned > 0, "correo sending abandonado")
    return success


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("api", "outbox", "test"))
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--state", type=Path, default=STATE)
    args = parser.parse_args()
    os.umask(0o077)
    try:
        token, chat = read_config(args.config)
        send = lambda message: send_telegram(token, chat, message)
        if args.mode == "test":
            return 0 if send("SkillMatch AI: alerta de prueba") else 1
        import fcntl  # Linux VPS only; imported here so pure logic tests run on Windows.

        lock_path = args.state.with_suffix(".lock")
        with lock_path.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = load_state(args.state)
            ok = run_check(args.mode, state, send, lambda: save_state(args.state, state))
        return 0 if ok else 1
    except (OSError, ValueError):
        # Exception text can include filesystem paths or provider URLs with tokens.
        print("Email monitor configuration or state error", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
