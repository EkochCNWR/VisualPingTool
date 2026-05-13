# PingChart

PingChart is a command-line network monitoring tool that pings one or more hosts and displays the results as a live terminal chart.

It supports single hosts, IP ranges, and CIDR subnets. In watch mode, PingChart refreshes in place without blinking or clearing the screen on every update.

## Features

- Ping a single host, multiple hosts, full IP ranges, or CIDR subnets
- Continuous live monitoring with `--watch`
- Smooth in-place terminal refresh
- Colored response bars
- Full-width chart that scales to your terminal window
- Shows reply count, timeout/loss count, unreachable count, and error count
- Displays average latency for successful replies
- Supports sorting by IP, latency, or status
- Cross-platform support for Windows, Linux, and macOS

## Requirements

- Python 3.8 or newer
- System `ping` command available in PATH

No third-party Python packages are required.

## Installation

Clone the repository:

```powershell
git clone https://github.com/EkochCNWR/VisualPingTool.git
cd VisualPingTool
```

Run the script directly:

```powershell
python .\pingchart.py 192.168.1.1
```

On Linux or macOS, you can optionally make it executable:

```bash
chmod +x pingchart.py
./pingchart.py 192.168.1.1
```

## Usage

```text
python pingchart.py [targets] [options]
```

Targets can be:

```text
192.168.1.1
8.8.8.8
google.com
192.168.1.0/24
192.168.1.1-192.168.1.254
```

You can pass multiple targets at once:

```powershell
python .\pingchart.py 8.8.8.8 1.1.1.1 192.168.1.0/24
```

## Examples

Ping a single host:

```powershell
python .\pingchart.py 8.8.8.8
```

Ping a full subnet:

```powershell
python .\pingchart.py 192.168.1.0/24
```

Ping a specific IP range:

```powershell
python .\pingchart.py 192.168.1.1-192.168.1.254
```

Ping each host 10 times:

```powershell
python .\pingchart.py 192.168.1.0/24 --count 10
```

Run in continuous monitoring mode:

```powershell
python .\pingchart.py 192.168.1.0/24 --watch
```

Refresh every 3 seconds:

```powershell
python .\pingchart.py 192.168.1.0/24 --watch --interval 3
```

Force colored output:

```powershell
python .\pingchart.py 192.168.1.0/24 --watch --color
```

Disable colored output:

```powershell
python .\pingchart.py 192.168.1.0/24 --watch --no-color
```

Sort by status:

```powershell
python .\pingchart.py 192.168.1.0/24 --sort status
```

Sort by latency:

```powershell
python .\pingchart.py 192.168.1.0/24 --sort latency
```

## Output Example

```text
Continuous ping mode - refresh every 3.0 seconds
Press Ctrl+C to stop.

Ping Response Status
================================================================================
Legend: █=Reply  ░=Loss/Timeout  ▒=Host Unreachable  ▓=Error/DNS/Unknown
--------------------------------------------------------------------------------
192.168.1.1      UP        2.1 ms    0.0% loss |████████████████████████|  R:20 L:0 U:0 E:0
192.168.1.10     MIXED    14.8 ms   25.0% loss |██████░░██████░░████████|  R:15 L:5 U:0 E:0
192.168.1.22     DOWN    timeout   100.0% loss |░░░░░░░░░░░░░░░░░░░░░░░░|  R:0 L:20 U:0 E:0
192.168.1.50     UNRCH   timeout   100.0% loss |▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒|  R:0 L:0 U:20 E:0
================================================================================
Total: 4   Up: 1   Mixed: 1   Unreachable: 1   Down: 1   Errors: 0
```

## Chart Legend

PingChart uses a block-style response chart.

| Symbol | Meaning |
|---|---|
| `█` | Reply received |
| `░` | Packet loss or timeout |
| `▒` | Host unreachable |
| `▓` | Error, DNS failure, or unknown response |

When color is enabled:

| Color | Meaning |
|---|---|
| Green | Reply received |
| Yellow | Packet loss or timeout |
| Red | Host unreachable |
| Magenta | Error, DNS failure, or unknown response |

## Columns Explained

```text
Host             Status   Avg Latency   Loss %       Response Bar      Counts
```

| Column | Description |
|---|---|
| Host | Hostname or IP address being pinged |
| Status | Overall status for the host |
| Avg Latency | Average latency for successful replies |
| Loss % | Percentage of failed ping attempts |
| Response Bar | Visual representation of each ping result |
| Counts | Totals for replies, losses, unreachable responses, and errors |

## Status Values

| Status | Meaning |
|---|---|
| `UP` | All ping attempts received replies |
| `MIXED` | Some replies were received, but some attempts failed |
| `DOWN` | No replies were received; attempts timed out or were lost |
| `UNRCH` | Host or network was reported as unreachable |
| `ERROR` | DNS failure, invalid host, or unknown ping error |

## Options

| Option | Description | Default |
|---|---|---|
| `targets` | Hosts, IPs, CIDRs, or ranges to ping | Required |
| `-c`, `--count` | Number of ping attempts per host | `5` |
| `-t`, `--timeout` | Timeout per ping in milliseconds | `1000` |
| `-w`, `--workers` | Number of concurrent worker threads | `64` |
| `--sort` | Sort by `ip`, `latency`, or `status` | `ip` |
| `--watch` | Continuously ping and refresh the chart | Disabled |
| `--interval` | Refresh interval in seconds for watch mode | `2.0` |
| `--color` | Force colored output | Disabled |
| `--no-color` | Disable colored output | Disabled |

## Notes About Full-Width Bars

The response bar expands to fit the width of your terminal window.

If you use a low count, such as `--count 5`, the chart stretches those 5 samples across the available space. For a more detailed chart, increase the count:

```powershell
python .\pingchart.py 192.168.1.1 --count 60
```

For subnet monitoring, a smaller count is usually faster:

```powershell
python .\pingchart.py 192.168.1.0/24 --watch --count 5 --interval 3
```

## Performance Tips

For small networks:

```powershell
python .\pingchart.py 192.168.1.0/24 --watch --count 5 --workers 64
```

For faster scans:

```powershell
python .\pingchart.py 192.168.1.0/24 --watch --count 3 --timeout 750 --workers 128
```

For larger networks, avoid overly aggressive settings. Scanning very large ranges with high concurrency may generate significant network traffic.

## Platform Notes

### Windows

PingChart works in PowerShell, Windows Terminal, and modern Command Prompt.

For the best experience, use Windows Terminal or PowerShell 7.

```powershell
python .\pingchart.py 192.168.1.0/24 --watch --color
```

### Linux and macOS

Run with Python 3:

```bash
python3 ./pingchart.py 192.168.1.0/24 --watch --color
```

You may also make it executable:

```bash
chmod +x pingchart.py
./pingchart.py 192.168.1.0/24 --watch --color
```

## Limitations

- Ping results depend on ICMP being allowed by the target host and network firewall.
- Some hosts may be online but configured to ignore ping requests.
- Host unreachable messages depend on the operating system and network path.
- Very large ranges may take time to scan and may create noticeable network traffic.
- The chart is a terminal visualization, not a historical log.
