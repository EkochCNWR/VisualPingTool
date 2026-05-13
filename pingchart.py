#!/usr/bin/env python3
import argparse
import ipaddress
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean


ANSI_RESET = "\033[0m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_MAGENTA = "\033[35m"


def expand_targets(target: str):
    target = target.strip()

    # CIDR range: 192.168.1.0/24
    if "/" in target:
        network = ipaddress.ip_network(target, strict=False)
        return [str(ip) for ip in network.hosts()]

    # Explicit range: 192.168.1.1-192.168.1.254
    if "-" in target:
        start, end = target.split("-", 1)
        start_ip = ipaddress.ip_address(start.strip())
        end_ip = ipaddress.ip_address(end.strip())

        if start_ip.version != end_ip.version:
            raise ValueError("Start and end IP versions do not match.")

        if int(end_ip) < int(start_ip):
            raise ValueError("End IP must be greater than start IP.")

        return [
            str(ipaddress.ip_address(i))
            for i in range(int(start_ip), int(end_ip) + 1)
        ]

    # Single IP or hostname
    return [target]


def classify_ping_failure(output: str):
    output_lower = output.lower()

    unreachable_indicators = [
        "destination host unreachable",
        "destination net unreachable",
        "destination network unreachable",
        "host unreachable",
        "network is unreachable",
        "no route to host",
    ]

    dns_indicators = [
        "could not find host",
        "name or service not known",
        "temporary failure in name resolution",
        "unknown host",
        "cannot resolve",
        "nodename nor servname provided",
    ]

    timeout_indicators = [
        "request timed out",
        "request timeout",
        "100% packet loss",
        "100.0% packet loss",
        "timed out",
    ]

    if any(text in output_lower for text in unreachable_indicators):
        return "unreachable"

    if any(text in output_lower for text in dns_indicators):
        return "error"

    if any(text in output_lower for text in timeout_indicators):
        return "loss"

    return "error"


def ping_once(host: str, timeout_ms: int):
    system = platform.system().lower()

    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
        latency_pattern = r"time[=<]\s*(\d+)\s*ms"
    else:
        timeout_sec = max(1, int(timeout_ms / 1000))
        cmd = ["ping", "-c", "1", "-W", str(timeout_sec), host]
        latency_pattern = r"time[=<]\s*([\d.]+)\s*ms"

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(2, timeout_ms / 1000 + 1),
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "loss",
            "latency_ms": None,
            "raw": "timeout",
        }

    output = result.stdout + result.stderr
    match = re.search(latency_pattern, output, re.IGNORECASE)

    if result.returncode == 0 and match:
        return {
            "status": "reply",
            "latency_ms": float(match.group(1)),
            "raw": output,
        }

    return {
        "status": classify_ping_failure(output),
        "latency_ms": None,
        "raw": output,
    }


def ping_host(host: str, count: int, timeout_ms: int):
    attempts = []
    latencies = []

    for _ in range(count):
        result = ping_once(host, timeout_ms)
        attempts.append(result["status"])

        if result["status"] == "reply" and result["latency_ms"] is not None:
            latencies.append(result["latency_ms"])

    reply_count = attempts.count("reply")
    loss_count = attempts.count("loss")
    unreachable_count = attempts.count("unreachable")
    error_count = attempts.count("error")

    failed_count = count - reply_count
    loss_pct = round(100 * failed_count / count, 1)

    if reply_count == count:
        overall_status = "UP"
    elif reply_count > 0:
        overall_status = "MIXED"
    elif unreachable_count == count:
        overall_status = "UNRCH"
    elif error_count == count:
        overall_status = "ERROR"
    else:
        overall_status = "DOWN"

    return {
        "host": host,
        "overall_status": overall_status,
        "attempts": attempts,
        "reply_count": reply_count,
        "loss_count": loss_count,
        "unreachable_count": unreachable_count,
        "error_count": error_count,
        "latency_ms": mean(latencies) if latencies else None,
        "loss_pct": loss_pct,
    }


def run_scan(hosts, args):
    results = []

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {
            executor.submit(ping_host, host, args.count, args.timeout): host
            for host in hosts
        }

        for future in as_completed(future_map):
            results.append(future.result())

    if args.sort == "latency":
        results.sort(
            key=lambda r: float("inf")
            if r["latency_ms"] is None
            else r["latency_ms"]
        )
    elif args.sort == "status":
        status_order = {
            "UP": 0,
            "MIXED": 1,
            "UNRCH": 2,
            "DOWN": 3,
            "ERROR": 4,
        }
        results.sort(
            key=lambda r: (
                status_order.get(r["overall_status"], 99),
                r["host"],
            )
        )
    else:
        try:
            results.sort(key=lambda r: ipaddress.ip_address(r["host"]))
        except ValueError:
            results.sort(key=lambda r: r["host"])

    return results


def should_use_color(args):
    if args.no_color:
        return False

    if args.color:
        return True

    return sys.stdout.isatty()


def block_for_attempt(status: str, use_color: bool):
    if status == "reply":
        block = "█"
        color = ANSI_GREEN
    elif status == "loss":
        block = "░"
        color = ANSI_YELLOW
    elif status == "unreachable":
        block = "▒"
        color = ANSI_RED
    else:
        block = "▓"
        color = ANSI_MAGENTA

    if use_color:
        return f"{color}{block}{ANSI_RESET}"

    return block


def make_response_bar(attempts, use_color: bool, width: int):
    if not attempts or width <= 0:
        return ""

    scaled = []

    for i in range(width):
        attempt_index = int(i * len(attempts) / width)
        attempt_index = min(attempt_index, len(attempts) - 1)
        scaled.append(block_for_attempt(attempts[attempt_index], use_color))

    return "".join(scaled)


def legend_item(block: str, color: str, label: str, use_color: bool):
    if use_color:
        return f"{color}{block}{ANSI_RESET}={label}"
    return f"{block}={label}"


def print_legend(use_color: bool):
    items = [
        legend_item("█", ANSI_GREEN, "Reply", use_color),
        legend_item("░", ANSI_YELLOW, "Loss/Timeout", use_color),
        legend_item("▒", ANSI_RED, "Host Unreachable", use_color),
        legend_item("▓", ANSI_MAGENTA, "Error/DNS/Unknown", use_color),
    ]

    print("Legend: " + "  ".join(items))


def visible_len(text: str):
    ansi_escape = re.compile(r"\033\[[0-9;?]*[A-Za-z]")
    return len(ansi_escape.sub("", text))


def print_chart(results, use_color: bool):
    if not results:
        print("No results.")
        return

    terminal_width = shutil.get_terminal_size((100, 20)).columns
    terminal_width = max(60, terminal_width)

    host_width = max(len(r["host"]) for r in results)
    host_width = min(max(host_width, 15), 40)

    divider_width = min(terminal_width, 160)

    print()
    print("Ping Response Status")
    print("=" * divider_width)
    print_legend(use_color)
    print("-" * divider_width)

    for r in results:
        host = r["host"][:host_width].ljust(host_width)
        status = r["overall_status"].ljust(5)

        if r["latency_ms"] is not None:
            latency = f"{r['latency_ms']:.1f} ms".rjust(10)
        else:
            latency = "timeout".rjust(10)

        loss = f"{r['loss_pct']:.1f}% loss".rjust(11)

        stats = (
            f"R:{r['reply_count']} "
            f"L:{r['loss_count']} "
            f"U:{r['unreachable_count']} "
            f"E:{r['error_count']}"
        )

        prefix = f"{host} {status} {latency} {loss} |"
        suffix = f"|  {stats}"

        available_width = terminal_width - visible_len(prefix) - visible_len(suffix)

        # Prevent wrapping on narrow windows.
        # If the terminal is very narrow, still show a small usable bar.
        bar_width = max(5, available_width)

        bar = make_response_bar(r["attempts"], use_color, bar_width)

        print(f"{prefix}{bar}{suffix}")

    total = len(results)
    up = sum(1 for r in results if r["overall_status"] == "UP")
    mixed = sum(1 for r in results if r["overall_status"] == "MIXED")
    unreachable = sum(1 for r in results if r["overall_status"] == "UNRCH")
    down = sum(1 for r in results if r["overall_status"] == "DOWN")
    errors = sum(1 for r in results if r["overall_status"] == "ERROR")

    print("=" * divider_width)
    print(
        f"Total: {total}   "
        f"Up: {up}   "
        f"Mixed: {mixed}   "
        f"Unreachable: {unreachable}   "
        f"Down: {down}   "
        f"Errors: {errors}"
    )


def clear_screen_once():
    os.system("cls" if platform.system().lower() == "windows" else "clear")


def move_cursor_home():
    print("\033[H", end="")


def clear_to_end_of_screen():
    print("\033[J", end="")


def hide_cursor():
    print("\033[?25l", end="")


def show_cursor():
    print("\033[?25h", end="")


def flush_output():
    sys.stdout.flush()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Ping hosts or full IP ranges and show a colored response-status chart."
    )

    parser.add_argument(
        "targets",
        nargs="+",
        help=(
            "Hosts, IPs, CIDRs, or ranges. Examples: "
            "8.8.8.8 192.168.1.0/24 192.168.1.1-192.168.1.254"
        ),
    )

    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=5,
        help="Ping count per host. Default: 5",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=1000,
        help="Timeout per ping in milliseconds. Default: 1000",
    )

    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=64,
        help="Concurrent workers. Default: 64",
    )

    parser.add_argument(
        "--sort",
        choices=["ip", "latency", "status"],
        default="ip",
        help="Sort output by ip, latency, or status. Default: ip",
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously ping and refresh the chart.",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Refresh interval in seconds when using --watch. Default: 2",
    )

    parser.add_argument(
        "--color",
        action="store_true",
        help="Force colored output.",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output.",
    )

    return parser.parse_args()


def validate_args(args):
    if args.count < 1:
        raise SystemExit("Error: --count must be at least 1.")

    if args.timeout < 100:
        raise SystemExit("Error: --timeout must be at least 100 milliseconds.")

    if args.workers < 1:
        raise SystemExit("Error: --workers must be at least 1.")

    if args.interval <= 0:
        raise SystemExit("Error: --interval must be greater than 0.")

    if args.color and args.no_color:
        raise SystemExit("Error: use either --color or --no-color, not both.")


def build_host_list(targets):
    all_hosts = []

    try:
        for target in targets:
            all_hosts.extend(expand_targets(target))
    except ValueError as error:
        raise SystemExit(f"Error: {error}")

    # Remove duplicates while preserving order
    return list(dict.fromkeys(all_hosts))


def run_once(all_hosts, args):
    use_color = should_use_color(args)
    results = run_scan(all_hosts, args)
    print_chart(results, use_color)


def run_watch(all_hosts, args):
    use_color = should_use_color(args)

    try:
        clear_screen_once()
        hide_cursor()

        while True:
            move_cursor_home()

            print(f"Continuous ping mode - refresh every {args.interval} seconds")
            print("Press Ctrl+C to stop.")

            results = run_scan(all_hosts, args)
            print_chart(results, use_color)

            clear_to_end_of_screen()
            flush_output()

            time.sleep(args.interval)

    except KeyboardInterrupt:
        show_cursor()
        print("\nStopped.")
    finally:
        show_cursor()
        flush_output()


def main():
    args = parse_args()
    validate_args(args)

    all_hosts = build_host_list(args.targets)

    if args.watch:
        run_watch(all_hosts, args)
    else:
        run_once(all_hosts, args)


if __name__ == "__main__":
    main()
