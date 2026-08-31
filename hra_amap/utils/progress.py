import re
import subprocess

from tqdm.auto import tqdm


BCPD_LOOP_RE = re.compile(r"\bloop=(\d+)\b")
BCPD_MAX_LOOPS_RE = re.compile(r"max #loops\s*=\s*(\d+)")
BCPD_SIGMA_RE = re.compile(r"\bsigma=([0-9.eE+-]+)")
BCPD_DIFF_RE = re.compile(r"\bdiff=([0-9.eE+-]+)")


def tqdm_or_iter(iterable, progress=True, **kwargs):
    return tqdm(iterable, **kwargs) if progress else iterable


def run_bcpd(args, cwd, max_iterations=None, progress=False):
    if not progress:
        return subprocess.run(args, cwd=str(cwd))

    process = subprocess.Popen(
        args,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    logs = []
    last_loop = 0
    bar = tqdm(
        total=max_iterations,
        desc="BCPD optimization",
        unit="loop",
        leave=False,
    )

    try:
        for line in process.stdout:
            logs.append(line)
            max_match = BCPD_MAX_LOOPS_RE.search(line)
            if max_match:
                total = int(max_match.group(1))
                if bar.total != total:
                    bar.total = total
                    bar.refresh()

            loop_match = BCPD_LOOP_RE.search(line)
            if not loop_match:
                continue

            loop = int(loop_match.group(1))
            bar.update(max(loop - last_loop, 0))
            last_loop = loop

            postfix = {}
            sigma_match = BCPD_SIGMA_RE.search(line)
            diff_match = BCPD_DIFF_RE.search(line)
            if sigma_match:
                postfix["sigma"] = sigma_match.group(1)
            if diff_match:
                postfix["diff"] = diff_match.group(1)
            if postfix:
                bar.set_postfix(postfix)

        returncode = process.wait()
    finally:
        bar.close()

    if returncode != 0:
        raise RuntimeError(
            "BCPD failed with return code "
            f"{returncode}.\n\nBCPD output:\n{''.join(logs)}"
        )

    return subprocess.CompletedProcess(args=args, returncode=returncode)
