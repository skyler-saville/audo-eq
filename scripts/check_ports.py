#!/usr/bin/env python3
"""Preflight check for Docker Compose published port collisions.

Resolves the effective Compose config for dev/prod, extracts published host
ports, and verifies they are available on this machine before startup.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import re
import socket
import subprocess
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check for host port collisions before docker compose up")
    parser.add_argument("--env-file", default=".env", help="Path to env file used by docker compose")
    parser.add_argument(
        "--example-file",
        default=".env.example",
        help="Path to env template used when creating env file",
    )
    parser.add_argument(
        "--mode",
        choices=["dev", "prod"],
        default="dev",
        help="Compose mode to resolve (determines override file)",
    )
    return parser.parse_args()


def compose_files_for_mode(mode: str) -> list[str]:
    base = ["compose.yaml"]
    if mode == "dev":
        base.append("compose.override.yaml")
    else:
        base.append("compose.prod.yaml")
    return base


def load_compose_config(env_file: str, mode: str) -> dict[str, Any]:
    files = compose_files_for_mode(mode)
    cmd = ["docker", "compose", "--env-file", env_file]
    for compose_file in files:
        cmd.extend(["-f", compose_file])
    cmd.extend(["config", "--format", "json"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError:
        print("ERROR: docker compose is not available in PATH.", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        msg = stderr or stdout or str(exc)
        print(f"ERROR: failed to resolve compose config: {msg}", file=sys.stderr)
        sys.exit(2)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print(f"ERROR: could not parse docker compose JSON output: {exc}", file=sys.stderr)
        sys.exit(2)


def parse_published_port(port_entry: Any) -> int | None:
    if isinstance(port_entry, dict):
        published = port_entry.get("published")
        if published is None:
            return None
        try:
            return int(str(published))
        except ValueError:
            return None

    if isinstance(port_entry, str):
        # Common short syntaxes:
        # 8000:8000, 127.0.0.1:8000:8000, 8000:8000/tcp, 8000
        value = port_entry
        if "/" in value:
            value = value.split("/", 1)[0]
        parts = value.split(":")
        if len(parts) == 1:
            # Only container port; host port assigned dynamically.
            return None
        # host may be [ip]:host:container or host:container
        host_port = parts[-2]
        try:
            return int(host_port)
        except ValueError:
            return None

    return None


def collect_published_ports(compose_config: dict[str, Any]) -> list[int]:
    ports: set[int] = set()
    services = compose_config.get("services", {})
    if not isinstance(services, dict):
        return []

    for service_cfg in services.values():
        if not isinstance(service_cfg, dict):
            continue
        for entry in service_cfg.get("ports", []) or []:
            port = parse_published_port(entry)
            if port is not None:
                ports.add(port)

    return sorted(ports)


def listening_tcp_ports() -> set[int]:
    ports: set[int] = set()

    # Linux path: ss is fast and typically available.
    try:
        ss = subprocess.run(["ss", "-Htanl"], capture_output=True, text=True, timeout=3)
    except subprocess.TimeoutExpired:
        ss = None

    # Some restricted environments return non-zero but still print listener data.
    if ss and ss.stdout.strip():
        for line in ss.stdout.splitlines():
            cols = line.split()
            if len(cols) < 4:
                continue
            local = cols[3]
            # Handles 0.0.0.0:8000, [::]:8000, [::1]:8000, etc.
            match = re.search(r":(\d+)$", local.strip("[]"))
            if match:
                ports.add(int(match.group(1)))
        return ports

    # Cross-platform fallback (macOS/BSD/Linux): lsof listener listing.
    try:
        lsof = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return ports
    if lsof.returncode == 0:
        for line in lsof.stdout.splitlines()[1:]:
            match = re.search(r":(\d+)\s+\(LISTEN\)$", line)
            if match:
                ports.add(int(match.group(1)))
        return ports

    return ports


def is_port_free(port: int, active_ports: set[int]) -> bool:
    if port in active_ports:
        return False

    # Last-resort check when listener commands are unavailable.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            return False
        if exc.errno in {errno.EPERM, errno.EACCES}:
            # Restricted environments may forbid bind probes; trust active scan.
            return True
        return False

    return True


def next_available_port(start: int, active_ports: set[int], reserved: set[int]) -> int:
    candidate = start
    while not is_port_free(candidate, active_ports) or candidate in reserved:
        candidate += 1
    return candidate


def env_port_keys_from_example(example_file: str) -> set[str]:
    if not os.path.exists(example_file):
        print(f"ERROR: env template not found: {example_file}", file=sys.stderr)
        sys.exit(2)
    with open(example_file, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    keys: set[str] = set()
    for line in lines:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.rstrip("\n"))
        if not match:
            continue
        key, raw_value = match.groups()
        if key.endswith("_PORT") and raw_value.strip().isdigit():
            keys.add(key)
    return keys


def parse_env_kv_lines(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.rstrip("\n"))
        if not match:
            continue
        key, raw_value = match.groups()
        values[key] = raw_value.strip()
    return values


def looks_like_secret_key(key: str) -> bool:
    secret_markers = (
        "SECRET",
        "PASSWORD",
        "TOKEN",
        "API_KEY",
        "ACCESS_KEY",
        "PRIVATE_KEY",
    )
    return any(marker in key for marker in secret_markers)


def warn_on_example_secret_values(env_file: str, example_file: str) -> None:
    with open(example_file, "r", encoding="utf-8") as handle:
        example_values = parse_env_kv_lines(handle.readlines())
    with open(env_file, "r", encoding="utf-8") as handle:
        env_values = parse_env_kv_lines(handle.readlines())

    matches: list[str] = []
    for key, example_value in example_values.items():
        if not looks_like_secret_key(key):
            continue
        if not example_value:
            continue
        env_value = env_values.get(key)
        if env_value is None:
            continue
        if env_value == example_value:
            matches.append(key)

    if matches:
        print("SECURITY WARNING: .env contains secret-like values that match .env.example defaults:")
        for key in matches:
            print(f"  - {key}")
        print("Suggestion: replace these values in .env with unique, non-default secrets.")


def rewrite_env_ports(
    env_file: str,
    lines: list[str],
    active_ports: set[int],
    port_keys: set[str],
    action_label: str,
) -> None:
    output_lines: list[str] = []
    changed_ports: list[tuple[str, int, int]] = []
    reserved: set[int] = set()

    for line in lines:
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.rstrip("\n"))
        if not match:
            output_lines.append(line)
            continue

        key, raw_value = match.groups()
        value = raw_value.strip()
        if key in port_keys and value.isdigit():
            original_port = int(value)
            selected_port = next_available_port(original_port, active_ports, reserved)
            reserved.add(selected_port)
            if selected_port != original_port:
                changed_ports.append((key, original_port, selected_port))
            output_lines.append(f"{key}={selected_port}\n")
            continue

        output_lines.append(line)

    with open(env_file, "w", encoding="utf-8") as handle:
        handle.writelines(output_lines)

    print(action_label)
    if changed_ports:
        for key, old, new in changed_ports:
            print(f"Adjusted {key}: {old} -> {new} (port in use)")
    else:
        print("No port adjustments needed.")


def ensure_env_ports(env_file: str, example_file: str, active_ports: set[int]) -> None:
    port_keys = env_port_keys_from_example(example_file)

    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        rewrite_env_ports(
            env_file=env_file,
            lines=lines,
            active_ports=active_ports,
            port_keys=port_keys,
            action_label=f"Updated {env_file} port assignments from existing file.",
        )
        return

    with open(example_file, "r", encoding="utf-8") as handle:
        lines = handle.readlines()
    rewrite_env_ports(
        env_file=env_file,
        lines=lines,
        active_ports=active_ports,
        port_keys=port_keys,
        action_label=f"Created {env_file} from {example_file}.",
    )


def main() -> int:
    args = parse_args()

    active_ports = listening_tcp_ports()
    ensure_env_ports(args.env_file, args.example_file, active_ports)

    if not os.path.exists(args.env_file):
        print(f"ERROR: env file not found: {args.env_file}", file=sys.stderr)
        return 2
    warn_on_example_secret_values(args.env_file, args.example_file)

    compose_config = load_compose_config(args.env_file, args.mode)
    ports = collect_published_ports(compose_config)

    if not ports:
        print(f"No published host ports detected for mode={args.mode}.")
        return 0

    busy = [port for port in ports if not is_port_free(port, active_ports)]

    print(f"Checked published host ports for mode={args.mode}: {', '.join(map(str, ports))}")
    if not busy:
        print("OK: no host port collisions detected.")
        return 0

    print(f"ERROR: port(s) already in use: {', '.join(map(str, busy))}", file=sys.stderr)
    print("Adjust .env port values or stop the conflicting process/container.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
