#!/usr/bin/env python3
"""Keep local information-source services alive only for a bounded skill command."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

SKILL = Path(__file__).resolve().parents[1]
LOCAL = SKILL / "local-sources"


def definitions():
    domestic = LOCAL / "domestic"
    xhs = LOCAL / "xiaohongshu"
    return {
        "rsshub": (domestic, [sys.executable, str(domestic / "run_rsshub.py")], 18200, "/"),
        "werss": (domestic, [str(domestic / "services/werss/.venv/bin/python"),
                            str(domestic / "run_werss.py")], 18001, "/api/openapi.json"),
        "xiaohongshu": (xhs, [sys.executable, str(xhs / "run_service.py")], 18060, "/health"),
    }


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=.3):
            return True
    except OSError:
        return False


def stop_group(process):
    # Use only the process group created by this invocation, including browser children.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=3)


@contextlib.contextmanager
def source_services(names):
    names = sorted(set(names))
    specs = definitions()
    if not names or any(name not in specs for name in names):
        raise ValueError("Choose rsshub, werss or xiaohongshu.")
    os.umask(0o077)
    owned = []
    with contextlib.ExitStack() as stack:
        try:
            for name in names:
                root, command, port, health_path = specs[name]
                runtime = root / "runtime"
                if not runtime.is_dir():
                    raise RuntimeError(f"{name}: local source is not installed.")
                lock = stack.enter_context((runtime / f"{name}-on-demand.lock").open("a"))
                deadline = time.monotonic() + 900
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() > deadline:
                            raise TimeoutError(f"{name}: another skill invocation is still using this source.")
                        time.sleep(.25)
                if port_open(port):
                    raise RuntimeError(f"{name}: port {port} is already in use; no unrelated process was stopped.")
                log = stack.enter_context((runtime / f"{name}-on-demand.log").open("a"))
                process = subprocess.Popen(command, cwd=root, stdout=log, stderr=log,
                                           start_new_session=True)
                owned.append((name, process, port))
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError(f"{name}: startup failed; inspect its private on-demand log.")
                    try:
                        with opener.open(f"http://127.0.0.1:{port}{health_path}", timeout=2) as response:
                            if response.status == 200:
                                break
                    except OSError:
                        pass
                    if time.monotonic() > deadline:
                        raise TimeoutError(f"{name}: startup timed out.")
                    time.sleep(.25)
            yield
        finally:
            for name, process, port in reversed(owned):
                stop_group(process)
                report = {"service": name, "mode": "on_demand", "stopped": not port_open(port),
                          "finished_at_unix": time.time()}
                (specs[name][0] / "runtime" / f"{name}-last-session.json").write_text(json.dumps(report))


def run_with_services(names, command, timeout=900):
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    old_handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)}
    child = None
    try:
        with source_services(names):
            try:
                child_env = os.environ.copy()
                if "xiaohongshu" in names:
                    settings = json.loads(
                        (LOCAL / "xiaohongshu/runtime/service.json").read_text())
                    child_env["XIAOHONGSHU_API_BASE"] = "http://127.0.0.1:18060"
                    child_env["XIAOHONGSHU_API_TOKEN"] = settings["token"]
                child = subprocess.Popen(command, start_new_session=True, env=child_env)
                return child.wait(timeout=timeout)
            finally:
                if child is not None:
                    stop_group(child)
    except KeyboardInterrupt:
        return 130
    except subprocess.TimeoutExpired:
        print("Source command timed out; temporary services were stopped.", file=sys.stderr)
        return 124
    except (RuntimeError, ValueError, TimeoutError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--services", required=True, help="Comma-separated rsshub,werss,xiaohongshu")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or args.timeout <= 0:
        parser.error("Provide a command after -- and a positive timeout.")
    return run_with_services(args.services.split(","), command, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
