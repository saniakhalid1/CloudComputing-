#!/usr/bin/env python3
"""
DS 584 - Assignment 02 - Milestone 04: Synthetic load generator
================================================================
Sends HTTP requests to the application through Nginx (http://localhost:8080/solve)
in phases. Each phase has a number of parallel "users" and a duration. Every user
sends one request after another (keep-alive connection), so more users = more load.

Default phases (about 13 minutes):
    LOW 5 users 60 s -> UP 20 / 50 / 100 / 150 users -> HOLD -> DOWN 50 / 10 users -> IDLE 0 users

Every 10 s it prints and saves to loadgen.csv:
    timestamp, users, requests in the last 10 s, requests/s, avg response time, errors

Usage:
    python3 loadgen.py                                   # default phases
    python3 loadgen.py --phases "10:60,100:120,0:120"    # users:seconds,users:seconds,...
    python3 loadgen.py --url http://localhost:8080/solve
Stop with Ctrl+C.
"""
import argparse
import csv
import http.client
import multiprocessing as mp
import os
import threading
import time
from datetime import datetime
from urllib.parse import urlparse

DEFAULT_PHASES = "5:60,20:60,50:90,100:120,150:120,50:90,10:60,0:150"
REPORT_EVERY = 10          # seconds
HERE = os.path.dirname(os.path.abspath(__file__))
LOG_CSV = os.path.join(HERE, "loadgen.csv")


def user(host, port, path, stop_at, counters):
    """One synthetic user: send requests one after another until stop_at."""
    ok, err, ms = counters
    conn = None
    while time.time() < stop_at:
        try:
            if conn is None:
                conn = http.client.HTTPConnection(host, port, timeout=10)
            t0 = time.time()
            conn.request("GET", path)
            resp = conn.getresponse()
            resp.read()
            took = (time.time() - t0) * 1000
            if resp.status == 200:
                with ok.get_lock():
                    ok.value += 1
                with ms.get_lock():
                    ms.value += took
            else:
                with err.get_lock():
                    err.value += 1
        except Exception:
            with err.get_lock():
                err.value += 1
            if conn is not None:
                conn.close()
            conn = None
            time.sleep(0.1)
    if conn is not None:
        conn.close()


def worker_process(n_users, host, port, path, stop_at, counters):
    """One process running n_users threads (several processes = several CPU cores)."""
    threads = [threading.Thread(target=user, args=(host, port, path, stop_at, counters),
                                daemon=True) for _ in range(n_users)]
    for t in threads:
        t.start()
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:          # Ctrl+C: daemon threads end with the process
        pass


def main():
    p = argparse.ArgumentParser(description="Synthetic load generator")
    p.add_argument("--url", default="http://localhost:8080/solve")
    p.add_argument("--phases", default=DEFAULT_PHASES,
                   help='"users:seconds,users:seconds,..." (default: %(default)s)')
    p.add_argument("--processes", type=int, default=min(os.cpu_count() or 2, 4),
                   help="processes used to send the load (default: up to 4)")
    a = p.parse_args()

    u = urlparse(a.url)
    host, port, path = u.hostname, u.port or 80, u.path or "/"
    phases = [tuple(int(x) for x in ph.split(":")) for ph in a.phases.split(",")]
    total = sum(s for _, s in phases)
    print(f"Load generator -> {a.url}")
    print("Phases: " + " | ".join(f"{n} users {s}s" for n, s in phases)
          + f"  (total {total // 60} min {total % 60} s)")

    counters = (mp.Value("L", 0), mp.Value("L", 0), mp.Value("d", 0.0))   # ok, errors, ms
    with open(LOG_CSV, "w", newline="") as f:
        csv.writer(f).writerow(["timestamp", "users", "requests", "requests_per_s",
                                "avg_response_ms", "errors"])

    last = [0, 0, 0.0]
    last_t = time.time()
    try:
        for n_users, seconds in phases:
            print(f"\n=== {datetime.now().strftime('%H:%M:%S')}  phase: {n_users} users "
                  f"for {seconds} s", flush=True)
            stop_at = time.time() + seconds
            procs = []
            if n_users > 0:
                n_proc = min(a.processes, n_users)
                share = [n_users // n_proc + (1 if i < n_users % n_proc else 0)
                         for i in range(n_proc)]
                for k in share:
                    pr = mp.Process(target=worker_process,
                                    args=(k, host, port, path, stop_at, counters))
                    pr.start()
                    procs.append(pr)

            while time.time() < stop_at:                       # report every 10 s
                time.sleep(min(REPORT_EVERY, max(stop_at - time.time(), 0)))
                now = time.time()
                ok, err, ms = counters[0].value, counters[1].value, counters[2].value
                d_ok, d_err, d_ms = ok - last[0], err - last[1], ms - last[2]
                dt = max(now - last_t, 1e-6)
                rps = d_ok / dt
                avg = d_ms / d_ok if d_ok else 0.0
                last, last_t = [ok, err, ms], now
                stamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                print(f"{stamp}  users={n_users:4d}  req/s={rps:8.1f}  "
                      f"avg={avg:7.1f} ms  errors={d_err}", flush=True)
                with open(LOG_CSV, "a", newline="") as f:
                    csv.writer(f).writerow([stamp, n_users, d_ok, f"{rps:.1f}",
                                            f"{avg:.2f}", d_err])
            for pr in procs:
                pr.join()
    except KeyboardInterrupt:
        print("\nStopped by user")
    print(f"\nTotal: {counters[0].value} requests OK, {counters[1].value} errors. "
          f"Log: {LOG_CSV}")


if __name__ == "__main__":
    main()
