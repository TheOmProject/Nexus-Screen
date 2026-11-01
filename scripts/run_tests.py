#!/usr/bin/env python3
"""Run the test suite safely on the Raspberry Pi: alone, under a memory watchdog.

  scripts/run_tests.py [TEST_FILE] [--min-avail MiB]     (default tests/test_print_controls.py, 350)

Refuses to start if another test run is active or memory is already low; kills the run (and
reports it) if MemAvailable falls below the threshold. Prints peak memory of the test process tree."""
import argparse, os, signal, subprocess, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = "/tmp/nexus-tests.lock"


def meminfo():
    d = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":")
        d[k] = int(v.split()[0]) // 1024
    return d


def tree_rss(pid):
    total, todo = 0, [pid]
    while todo:
        p = todo.pop()
        try:
            total += int([l for l in open(f"/proc/{p}/status") if l.startswith("VmRSS")][0].split()[1])
            todo += [int(c) for c in open(f"/proc/{p}/task/{p}/children").read().split()]
        except (OSError, IndexError):
            pass
    return total // 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("test", nargs="?", default="tests/test_print_controls.py")
    ap.add_argument("--min-avail", type=int, default=350)
    args = ap.parse_args()
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
    except FileExistsError:
        other = open(LOCK).read().strip()
        if other and os.path.exists(f"/proc/{other}"):
            sys.exit(f"another test run is active (pid {other}) — not starting a second one")
        os.remove(LOCK)
        return main()
    try:
        m = meminfo()
        if m["MemAvailable"] < args.min_avail + 150:
            sys.exit(f"only {m['MemAvailable']} MiB available — not starting (need {args.min_avail + 150})")
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        proc = subprocess.Popen([sys.executable, args.test], cwd=HERE, env=env,
                                start_new_session=True)
        start, peak, low, t0, killed = m["MemAvailable"], 0, m["MemAvailable"], time.time(), False
        while proc.poll() is None:
            peak = max(peak, tree_rss(proc.pid))
            low = min(low, meminfo()["MemAvailable"])
            if low < args.min_avail:
                os.killpg(proc.pid, signal.SIGKILL); killed = True
                break
            time.sleep(0.5)
        proc.wait()
        print(f"\n[run_tests] exit={proc.returncode} {'KILLED by memory watchdog ' if killed else ''}"
              f"duration={time.time() - t0:.0f}s peak_test_rss={peak} MiB "
              f"MemAvailable start={start} min={low} MiB (threshold {args.min_avail})", flush=True)
        return 1 if killed else proc.returncode
    finally:
        os.remove(LOCK)


if __name__ == "__main__":
    sys.exit(main())
