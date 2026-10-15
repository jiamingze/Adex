"""Run a CI gate without hiding its exit status; annotate bounded failure context."""

from collections import deque
import subprocess
import sys


def main(args):
    if not args:
        raise SystemExit("Usage: python scripts/ci_run.py COMMAND [ARG ...]")
    tail = deque(maxlen=60)
    with subprocess.Popen(
        args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    ) as child:
        for line in child.stdout:
            print(line, end="", flush=True)
            tail.append(line)
        status = child.wait()
    if status:
        # GitHub truncates long annotations. Preserve the final error/summary,
        # while the complete command output remains in the normal job log.
        context = "".join(tail)[-3000:]
        escaped = context.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print("::error title=CI command failed::" + escaped, flush=True)
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
