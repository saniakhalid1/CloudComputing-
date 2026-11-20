#!/usr/bin/env python3
"""
DS 584 - Assignment 02 - Milestone 04: Autoscaler
=================================================
One standalone program that runs on the host machine and does three things in a loop:

  Part A  Every 10 s: read CPU and memory of every application container with
          'docker stats' and append one row to metrics.csv.

  Part B  Read the last 3 rows of metrics.csv and decide:
            all 3 rows avg_cpu > 70 %  (= above 70 % for 30 s)  -> scale OUT (+1 container)
            all 3 rows avg_cpu < 30 %  (= below 30 % for 30 s)  -> scale IN  (-1 container)
          Always between MIN (1) and MAX (4) containers.
          After any scaling operation: wait COOLDOWN (30 s) before the next one.

  Part C  Keep Nginx up to date:
            scale out : start container -> wait until it answers -> add to upstream.conf
                        -> test config (nginx -t) -> reload Nginx
            scale in  : remove from upstream.conf -> test + reload Nginx (no new requests)
                        -> wait DRAIN seconds (running requests finish) -> stop -> remove
            every cycle: only containers that answer health checks stay in upstream.conf

Usage:
    python3 autoscaler.py                      # default settings below
    python3 autoscaler.py --cooldown 60        # any setting can be changed
    python3 autoscaler.py --help
Stop with Ctrl+C (containers and Nginx keep running).
"""
import argparse
import csv
import os
import re
import shutil
import subprocess
import time
from datetime import datetime

# ------------------------------------------------------------------ settings
MIN_CONTAINERS = 1        # never fewer than this
MAX_CONTAINERS = 4        # never more than this
SCALE_OUT_CPU = 70.0      # % (100 % = one full CPU core, the container limit)
SCALE_IN_CPU = 30.0       # %
WINDOW = 3                # consecutive CSV rows that must agree (3 x 10 s = 30 s)
INTERVAL = 10             # seconds between two CSV rows
COOLDOWN = 30             # seconds to wait after a scaling operation
DRAIN = 10                # seconds a removed container may finish its requests

IMAGE = "quad-app"        # application image (Milestone 2)
NETWORK = "quadnet"       # Docker network shared with Nginx
NGINX = "nginx"           # Nginx container name (Milestone 3)
APP_PORT = 5000
CPU_LIMIT = "1"           # each container: 1 CPU
MEM_LIMIT = "1g"          # each container: 1 GB

HERE = os.path.dirname(os.path.abspath(__file__))
METRICS_CSV = os.path.join(HERE, "metrics.csv")
UPSTREAM_CONF = os.path.join(HERE, "nginx", "conf.d", "upstream.conf")
TIME_FORMAT = "%d-%m-%Y %H:%M:%S"
APP_NAME = re.compile(r"^app(\d+)$")


def log(text):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {text}", flush=True)


def run(*cmd):
    """Run a command, return (ok, output)."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


# ------------------------------------------------------------------ containers
def app_containers():
    """Names of the running application containers, sorted: app1, app2, ..."""
    ok, out = run("docker", "ps", "--format", "{{.Names}}")
    names = [n for n in out.splitlines() if APP_NAME.match(n)]
    return sorted(names, key=lambda n: int(APP_NAME.match(n).group(1)))


def next_name(running):
    i = 1
    while f"app{i}" in running:
        i += 1
    return f"app{i}"


def is_healthy(name):
    """Ask the container for /solve from inside the Nginx container
    (the same path real requests take)."""
    ok, _ = run("docker", "exec", NGINX, "wget", "-q", "-O", "/dev/null", "-T", "3",
                f"http://{name}:{APP_PORT}/solve")
    return ok


# ------------------------------------------------------------------ Part A: metrics
def docker_stats(names):
    """{name: (cpu %, memory %)} from 'docker stats --no-stream'."""
    if not names:
        return {}
    ok, out = run("docker", "stats", "--no-stream", "--format",
                  "{{.Name}},{{.CPUPerc}},{{.MemPerc}}", *names)
    stats = {}
    for line in out.splitlines():
        parts = line.split(",")
        if len(parts) == 3 and parts[0] in names:
            try:
                stats[parts[0]] = (float(parts[1].rstrip("%")), float(parts[2].rstrip("%")))
            except ValueError:            # "--" while a container is starting
                stats[parts[0]] = (0.0, 0.0)
    return stats


def start_csv():
    """Create metrics.csv with its header (an old file is kept as a backup)."""
    if os.path.exists(METRICS_CSV):
        backup = METRICS_CSV.replace(".csv", datetime.now().strftime("_old_%Y%m%d_%H%M%S.csv"))
        shutil.move(METRICS_CSV, backup)
        log(f"Old metrics.csv saved as {os.path.basename(backup)}")
    header = ["timestamp", "container_count", "avg_cpu", "avg_memory"]
    for i in range(1, MAX_CONTAINERS + 1):
        header += [f"app{i}_cpu", f"app{i}_memory"]
    header += ["action"]
    with open(METRICS_CSV, "w", newline="") as f:
        csv.writer(f).writerow(header)


def write_row(names, stats):
    """Append one row to metrics.csv and return the average CPU."""
    cpus = [stats[n][0] for n in names if n in stats]
    mems = [stats[n][1] for n in names if n in stats]
    avg_cpu = sum(cpus) / len(cpus) if cpus else 0.0
    avg_mem = sum(mems) / len(mems) if mems else 0.0
    row = [datetime.now().strftime(TIME_FORMAT), len(names), f"{avg_cpu:.2f}", f"{avg_mem:.2f}"]
    for i in range(1, MAX_CONTAINERS + 1):
        s = stats.get(f"app{i}")
        row += [f"{s[0]:.2f}", f"{s[1]:.2f}"] if s else ["", ""]
    row += [""]                                     # action is filled in after the decision
    with open(METRICS_CSV, "a", newline="") as f:
        csv.writer(f).writerow(row)
    return avg_cpu, avg_mem


def set_last_action(action):
    """Write the decision into the 'action' column of the last row."""
    with open(METRICS_CSV, newline="") as f:
        rows = list(csv.reader(f))
    rows[-1][-1] = action
    with open(METRICS_CSV, "w", newline="") as f:
        csv.writer(f).writerows(rows)


# ------------------------------------------------------------------ Part B: decision
def last_rows(n):
    """The last n data rows of metrics.csv."""
    with open(METRICS_CSV, newline="") as f:
        return list(csv.DictReader(f))[-n:]


def decide(count, last_scale_time):
    """Read the last WINDOW rows of metrics.csv and return (action, reason)."""
    rows = last_rows(WINDOW)
    # only rows measured with the current number of containers count
    rows = [r for r in rows if int(r["container_count"]) == count]
    cpus = [float(r["avg_cpu"]) for r in rows]
    shown = " / ".join(f"{c:.1f}" for c in cpus)

    if len(cpus) < WINDOW:
        return "wait", f"only {len(cpus)} of {WINDOW} rows with {count} container(s) so far"

    wait = COOLDOWN - (time.time() - last_scale_time)
    if all(c > SCALE_OUT_CPU for c in cpus):
        if count >= MAX_CONTAINERS:
            return "at_max", f"CPU {shown} > {SCALE_OUT_CPU:.0f}% but already {MAX_CONTAINERS}"
        if wait > 0:
            return "cooldown", f"CPU {shown} > {SCALE_OUT_CPU:.0f}%, cooldown {wait:.0f} s left"
        return "scale_out", f"CPU {shown} > {SCALE_OUT_CPU:.0f}% for {WINDOW} rows"

    if all(c < SCALE_IN_CPU for c in cpus):
        if count <= MIN_CONTAINERS:
            return "at_min", f"CPU {shown} < {SCALE_IN_CPU:.0f}% but already {MIN_CONTAINERS}"
        if wait > 0:
            return "cooldown", f"CPU {shown} < {SCALE_IN_CPU:.0f}%, cooldown {wait:.0f} s left"
        return "scale_in", f"CPU {shown} < {SCALE_IN_CPU:.0f}% for {WINDOW} rows"

    return "none", f"CPU {shown} between {SCALE_IN_CPU:.0f}% and {SCALE_OUT_CPU:.0f}%"


# ------------------------------------------------------------------ Part C: Nginx
def upstream_names():
    """Containers currently listed in upstream.conf."""
    try:
        with open(UPSTREAM_CONF) as f:
            return re.findall(r"server\s+(app\d+):", f.read())
    except FileNotFoundError:
        return []


def update_nginx(names, reason):
    """Write upstream.conf, test it, reload Nginx. Restore the old file if the test fails."""
    old = open(UPSTREAM_CONF).read() if os.path.exists(UPSTREAM_CONF) else ""
    new = (f"# Generated by autoscaler.py - {datetime.now().strftime(TIME_FORMAT)}\n"
           "upstream app_servers {\n"
           + "".join(f"    server {n}:{APP_PORT} max_fails=3 fail_timeout=10s;\n" for n in names)
           + "    keepalive 32;\n}\n")
    with open(UPSTREAM_CONF, "w") as f:          # same file is mounted inside Nginx
        f.write(new)
    ok, out = run("docker", "exec", NGINX, "nginx", "-t")
    if not ok:
        with open(UPSTREAM_CONF, "w") as f:
            f.write(old)
        log(f"  nginx -t FAILED, old configuration restored: {out}")
        return False
    run("docker", "exec", NGINX, "nginx", "-s", "reload")   # graceful: no request is dropped
    log(f"  Nginx reloaded ({reason}) -> upstream: {', '.join(names)}")
    return True


# ------------------------------------------------------------------ scaling
def scale_out(running):
    name = next_name(running)
    log(f"SCALE OUT {len(running)} -> {len(running) + 1}: starting {name}")
    run("docker", "rm", "-f", name)                          # leftover with same name
    ok, out = run("docker", "run", "-d", "--name", name, "--network", NETWORK,
                  f"--cpus={CPU_LIMIT}", f"--memory={MEM_LIMIT}", IMAGE)
    if not ok:
        log(f"  could not start {name}: {out}")
        return False
    for second in range(30):                                 # wait until it answers
        if is_healthy(name):
            log(f"  {name} is healthy after {second + 1} s")
            return update_nginx(upstream_names() + [name], f"added {name}")
        time.sleep(1)
    log(f"  {name} did not answer within 30 s - removing it")
    run("docker", "rm", "-f", name)
    return False


def scale_in(running):
    name = running[-1]                                       # newest container
    log(f"SCALE IN {len(running)} -> {len(running) - 1}: removing {name}")
    remaining = [n for n in upstream_names() if n != name] or running[:-1]
    if not update_nginx(remaining, f"removed {name}"):       # 1. no new requests
        return False
    log(f"  draining {name} for {DRAIN} s")
    time.sleep(DRAIN)                                        # 2. running requests finish
    run("docker", "stop", "-t", "10", name)                  # 3. graceful stop
    run("docker", "rm", name)                                # 4. remove
    log(f"  {name} stopped and removed")
    return True


# ------------------------------------------------------------------ health (Part C.2)
fail_count = {}


def health_sync(running):
    """Only healthy containers stay in Nginx. A container is taken out after 3 failed
    checks in a row and put back as soon as it answers again."""
    healthy = []
    for n in running:
        if is_healthy(n):
            fail_count[n] = 0
        else:
            fail_count[n] = fail_count.get(n, 0) + 1
            log(f"  health check failed for {n} ({fail_count[n]}/3)")
        if fail_count[n] < 3:
            healthy.append(n)
    if not healthy:                       # never leave Nginx with an empty list
        return
    if sorted(healthy) != sorted(upstream_names()):
        update_nginx(healthy, "health check")


# ------------------------------------------------------------------ main loop
def main():
    global MIN_CONTAINERS, MAX_CONTAINERS, COOLDOWN, INTERVAL, DRAIN
    p = argparse.ArgumentParser(description="Milestone 4 autoscaler")
    p.add_argument("--min", type=int, default=MIN_CONTAINERS)
    p.add_argument("--max", type=int, default=MAX_CONTAINERS)
    p.add_argument("--cooldown", type=int, default=COOLDOWN, help="seconds (default 30)")
    p.add_argument("--interval", type=int, default=INTERVAL, help="seconds (default 10)")
    p.add_argument("--drain", type=int, default=DRAIN, help="seconds (default 10)")
    a = p.parse_args()
    MIN_CONTAINERS, MAX_CONTAINERS = a.min, a.max
    COOLDOWN, INTERVAL, DRAIN = a.cooldown, a.interval, a.drain

    log(f"Autoscaler started: {MIN_CONTAINERS}-{MAX_CONTAINERS} containers, "
        f"scale out > {SCALE_OUT_CPU:.0f}%, scale in < {SCALE_IN_CPU:.0f}%, "
        f"{WINDOW} rows x {INTERVAL} s, cooldown {COOLDOWN} s, drain {DRAIN} s")

    ok, state = run("docker", "inspect", "-f", "{{.State.Running}}", NGINX)
    if state != "true":
        log("ERROR: the Nginx container is not running. Start it first (Milestone 3).")
        return

    start_csv()
    running = app_containers()
    while len(running) < MIN_CONTAINERS:                     # enforce the minimum
        scale_out(running)
        running = app_containers()
    update_nginx(running, "start-up")
    last_scale = 0.0

    try:
        while True:
            t0 = time.time()
            running = app_containers()

            health_sync(running)                             # Part C.2

            stats = docker_stats(running)                    # Part A
            avg_cpu, avg_mem = write_row(running, stats)
            log(f"containers={len(running)}  avg_cpu={avg_cpu:6.2f}%  avg_mem={avg_mem:5.2f}%  "
                + "  ".join(f"{n}={stats[n][0]:.1f}%" for n in running if n in stats))

            action, reason = decide(len(running), last_scale)    # Part B
            log(f"  decision: {action} ({reason})")
            if action == "scale_out" and scale_out(running):
                last_scale = time.time()
            elif action == "scale_in" and scale_in(running):
                last_scale = time.time()
            set_last_action(action)

            time.sleep(max(INTERVAL - (time.time() - t0), 0))
    except KeyboardInterrupt:
        log(f"Stopped. Metrics are in {METRICS_CSV}")


if __name__ == "__main__":
    main()
