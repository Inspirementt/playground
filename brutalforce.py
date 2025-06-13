import itertools
import string
import time
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.console import Group
from rich.padding import Padding
from rich.color import Color

HEADER = r"""
                                (                         
   (                 )       (  )\ )                      
 ( )\  (      (   ( /(    )  )\(()/(      (           (   
 )((_) )(    ))\  )\())( /( ((_)/(_)) (   )(    (    ))\  
((_)_ (()\  /((_)(_))/ )(_)) _ (_))_| )\ (()\   )\  /((_) 
 | _ ) ((_)(_))( | |_ ((_)_ | || |_  ((_) ((_) ((_)(_))   
 | _ \| '_|| || ||  _|/ _` || || __|/ _ \| '_|/ _| / -_)  
 |___/|_|   \_,_| \__|\__,_||_||_|  \___/|_|  \__| \___|  
                                                            
"""

digits = string.digits + string.ascii_lowercase + string.ascii_uppercase + "!@#$%^&*()-_=+[]{}|;:,.<>?"

windows = [300, 600, 900]  # 5, 10, 15 min in seconds

start_time = time.time()
count = 0
length = 1
peak_aps = 0
attempt_times = []
found_time = None
found_duration = None

# Ask for password input
target_password = input("Enter password to track progress to (leave empty to skip): ").strip()
track_target = bool(target_password)

def format_time_human(seconds):
    # Constants
    SECOND = 1
    MINUTE = 60 * SECOND
    HOUR = 60 * MINUTE
    DAY = 24 * HOUR
    MONTH = 30 * DAY
    YEAR = 365 * DAY
    BILLION_YEAR = 1_000_000_000 * YEAR
    TRILLION_YEAR = 1_000_000_000_000 * YEAR

    seconds = int(seconds)
    if seconds <= 0:
        return "0s"

    if seconds >= TRILLION_YEAR:
        years = seconds / TRILLION_YEAR
        remainder = seconds % TRILLION_YEAR
        months = (remainder // MONTH) % 12
        days = (remainder % MONTH) // DAY
        return f"{years:.3f} T years {months} months {days} days"
    elif seconds >= BILLION_YEAR:
        years = seconds / BILLION_YEAR
        remainder = seconds % BILLION_YEAR
        months = (remainder // MONTH) % 12
        days = (remainder % MONTH) // DAY
        return f"{years:.3f} B years {months} months {days} days"
    elif seconds >= YEAR:
        years = seconds // YEAR
        remainder = seconds % YEAR
        months = (remainder // MONTH) % 12
        days = (remainder % MONTH) // DAY
        return f"{years} years {months} months {days} days"

    # Less than a year fallback
    intervals = (
        ('d', DAY),
        ('h', HOUR),
        ('m', MINUTE),
        ('s', SECOND),
    )

    parts = []
    for name, count in intervals:
        value = seconds // count
        if value > 0:
            parts.append(f"{value}{name}")
            seconds -= value * count
        if len(parts) == 3:
            break
    return ' '.join(parts)

def password_to_index(password, charset):
    base = len(charset)
    index = 0
    for i, char in enumerate(reversed(password)):
        try:
            power = base ** i
            index += charset.index(char) * power
        except ValueError:
            return None
    return index

target_index = password_to_index(target_password, digits) if track_target else None

def format_time(seconds):
    mins, secs = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def calculate_avg_aps(window):
    cutoff = time.time() - window
    relevant = [(t, c) for t, c in attempt_times if t >= cutoff]
    if not relevant:
        return 0.0
    t0, c0 = relevant[0]
    t1, c1 = attempt_times[-1]
    elapsed = t1 - t0
    if elapsed == 0:
        return 0.0
    return (c1 - c0) / elapsed

def human_readable(n):
    abs_n = abs(n)
    if abs_n < 1000:
        return str(n)
    for unit in ['k', 'M', 'B', 'T']:
        abs_n /= 1000.0
        if abs_n < 1000:
            return f"{n/1000**(['', 'k', 'M', 'B', 'T'].index(unit)):.2f} {unit}"
    return str(n)

def gradient_text(text: str, start_color: str, end_color: str) -> Text:
    lines = text.splitlines()
    n = len(lines)
    start = Color.parse(start_color).triplet
    end = Color.parse(end_color).triplet

    def interpolate(c1, c2, factor):
        return int(c1 + (c2 - c1) * factor)

    gradient_lines = Text()
    for i, line in enumerate(lines):
        factor = i / max(n - 1, 1)
        r = interpolate(start[0], end[0], factor)
        g = interpolate(start[1], end[1], factor)
        b = interpolate(start[2], end[2], factor)
        color = f"#{r:02x}{g:02x}{b:02x}"
        gradient_lines.append(line + "\n", style=color)
    return gradient_lines

def make_dashboard(current_attempt, attempts_per_sec):
    elapsed = (found_time if found_time else time.time()) - start_time
    global peak_aps
    if attempts_per_sec > peak_aps:
        peak_aps = attempts_per_sec

    attempt_times.append((time.time(), count))
    cutoff = time.time() - max(windows)
    while attempt_times and attempt_times[0][0] < cutoff:
        attempt_times.pop(0)

    avg_5 = calculate_avg_aps(windows[0])
    avg_10 = calculate_avg_aps(windows[1])
    avg_15 = calculate_avg_aps(windows[2])

    table = Table.grid(padding=1)
    table.add_column(justify="right")
    table.add_column(justify="left", style="cyan")

    table.add_row("Start Time:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)))
    table.add_row("Elapsed:", format_time(elapsed))
    table.add_row("Current Attempt:", f"[bold yellow]{current_attempt}[/bold yellow]")
    table.add_row("Total Attempts:", f"{count} ({human_readable(count)})")
    table.add_row("Attempts/sec (live):", f"{attempts_per_sec:.2f} ({human_readable(attempts_per_sec)})")
    table.add_row("Peak Attempts/sec:", f"{peak_aps:.2f} ({human_readable(peak_aps)})")
    table.add_row("Avg Attempts/sec (5m):", f"{avg_5:.2f} ({human_readable(avg_5)})")
    table.add_row("Avg Attempts/sec (10m):", f"{avg_10:.2f} ({human_readable(avg_10)})")
    table.add_row("Avg Attempts/sec (15m):", f"{avg_15:.2f} ({human_readable(avg_15)})")

    if track_target and target_index is not None:
        if count < target_index:
            attempts_left = target_index - count
            if avg_5 > 0:
                est_time = attempts_left / avg_5
                eta_str = format_time_human(est_time)  # Changed here
            else:
                eta_str = "N/A"
            table.add_row("Target Password:", f"[bold]{target_password}[/bold]")
            table.add_row("Progress to Target:", f"{count}/{target_index} ({(count/target_index)*100:.2f}%)")
            table.add_row("ETA to Target:", eta_str)
        elif count >= target_index:
            table.add_row("Target Password:", f"[bold green]{target_password}[/bold green]")
            table.add_row("Status:", "[bold green]FOUND![/bold green]")  
            if found_duration is not None:
                table.add_row("Time to Find:", format_time_human(found_duration))  # And here

    gradient_header = gradient_text(HEADER, start_color="#FF0000", end_color="#FFFF00")

    group = Group(
        Align.center(gradient_header),
        Padding(table, (1, 2)),
    )
    return Panel(group, title="BrutalForce 3000", border_style="bright_magenta")

def main():
    global count, length, found_time, found_duration
    last_update = 0
    update_interval = 0.2  # seconds between dashboard updates

    with Live(make_dashboard("", 0), refresh_per_second=5, screen=True) as live:
        while True:
            for combo in itertools.product(digits, repeat=length):
                attempt = ''.join(combo)
                count += 1
                now = time.time()
                if now - last_update > update_interval:
                    elapsed = now - start_time
                    attempts_per_sec = count / elapsed if elapsed > 0 else 0
                    live.update(make_dashboard(attempt, attempts_per_sec))
                    last_update = now
                if track_target and attempt == target_password:
                    if found_time is None:
                        found_time = time.time()
                        found_duration = found_time - start_time

            length += 1

if __name__ == "__main__":
    main()
