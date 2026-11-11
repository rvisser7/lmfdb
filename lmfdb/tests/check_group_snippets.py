#!/usr/bin/env python3
"""
Run the code snippets of every LMFDB abstract group page and report the ones that fail.

For each group with a GAP label N.i (sorted by order N, then GAP id i) and each requested
language, this fetches

    Groups/Abstract/<label>/codedownload/<lang>

splits it into its snippet blocks (one per "<comment> <description>:" header written by
CodeSnippet.export_code), and runs the blocks in a persistent CAS session, using the same
process set-up as generate_snippet_tests.py (exec_dict, prompts, Magma SetPrompt trick, CHIMP).
A block fails if its output contains an error, it times out, the CAS crashes, or it leaves an
unfinished statement behind. Warnings (deprecations, GAP "Syntax warning", ...) are reported
separately.

Between groups the session namespace is cleared, so a snippet that relies on a variable it never
defines is not masked by a leftover from the previous group:
  * sage / sage_gap: reset()
  * oscar:           every group runs in a fresh anonymous module (with REPL soft-scope semantics)
  * gap / magma:     every name assigned with := in the previous group is unbound / deleted

Typical use, from the LMFDB root, in the environment you use for generate_snippet_tests.py
(run one process per language in parallel, they are independent):

    sage -python lmfdb/tests/check_group_snippets.py -l gap --max-order 64
    sage -python lmfdb/tests/check_group_snippets.py -l magma --chimp ~/CHIMP --resume
    sage -python lmfdb/tests/check_group_snippets.py -l oscar --start 96.1 --max-order 200
    sage -python lmfdb/tests/check_group_snippets.py -l sage --labels 8.4 32.14 60.5
    sage -python lmfdb/tests/check_group_snippets.py -l gap --summary-only

Output, per language, in <outdir>/<lang>/ (default outdir: snippet_check/):
    results.jsonl     one JSON record per group checked (label, status, failing blocks with code + output)
    summary.md        failing blocks grouped by snippet description, with example labels and the first error
    cache/<label>.txt the downloaded snippet files (reused on later runs unless --refetch)
"""

import argparse
import base64
import datetime
import importlib.util
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import pexpect

HERE = Path(__file__).resolve().parent
LMFDB_ROOT = HERE.parents[1]
if str(LMFDB_ROOT) not in sys.path:
    sys.path.insert(0, str(LMFDB_ROOT))


def _load_snippet_test_module():
    # Load generate_snippet_tests.py by path, so that importing it does not pull in
    # lmfdb/tests/__init__.py (which starts the app) before we need it.
    spec = importlib.util.spec_from_file_location("generate_snippet_tests", HERE / "generate_snippet_tests.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gst = _load_snippet_test_module()

LANGS = ["magma", "gap", "sage", "sage_gap", "oscar"]
GAP_LABEL_RE = re.compile(r"^(\d+)\.(\d+)$")
ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

ERROR_RE = {
    "gap": re.compile(r"^\s*(Error|Syntax error)\b|\bError, |^brk>", re.M),
    "magma": re.compile(r"\b(Runtime|User|Internal|System|Syntax) error\b|^\s*>> ", re.M | re.I),
    "sage": re.compile(r"Traceback \(most recent call last\)|^\s*[A-Za-z_]*(Error|Exception)\b|\b[A-Z]\w*Error:", re.M),
    "oscar": re.compile(r"^\s*ERROR:", re.M),
}
ERROR_RE["sage_gap"] = ERROR_RE["sage"]

WARNING_RE = {
    "gap": re.compile(r"Syntax warning|^#W ", re.M),
    "magma": re.compile(r"\bWarning:", re.I),
    "sage": re.compile(r"\b[A-Z]\w*Warning\b"),
    "oscar": re.compile(r"\bWarning:"),
}
WARNING_RE["sage_gap"] = WARNING_RE["sage"]

FAIL_STATUSES = ("error", "timeout", "crash", "incomplete")

# Words that can show up to the left of := without being assigned variables
GAP_MAGMA_KEYWORDS = {
    "and", "assert", "by", "case", "cat", "do", "elif", "else", "end", "eq", "error", "false", "fi",
    "for", "forall", "function", "ge", "gt", "if", "in", "is", "le", "local", "lt", "ne", "not", "od",
    "or", "procedure", "rec", "repeat", "return", "select", "then", "true", "until", "when", "where",
    "while",
}
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def label_key(label):
    n, i = GAP_LABEL_RE.match(label).groups()
    return (int(n), int(i))


def clean(text):
    return ANSI_RE.sub("", text or "").replace("\r\n", "\n").replace("\r", "")


def truncate(text, limit):
    if limit <= 0 or len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n[... {len(text) - limit} characters omitted ...]\n" + text[-half:]


# ---------------------------------------------------------------------------
# Parsing the codedownload files
# ---------------------------------------------------------------------------

def parse_blocks(text, cmt):
    """
    Split a codedownload file into [(description, code)].

    CodeSnippet.export_code writes each snippet as a blank line, then the header
    "<cmt> <description>: ", then the code; the frontmatter before the first header is ignored.
    """
    header = re.compile(r"^" + re.escape(cmt) + r" (.+?):\s*$")
    blocks = []
    current = None
    previous_blank = True
    for line in text.splitlines():
        match = header.match(line)
        if match and previous_blank:
            current = (match.group(1).strip(), [])
            blocks.append(current)
        elif current is not None:
            current[1].append(line)
        previous_blank = not line.strip()
    return [(name, "\n".join(lines).strip("\n")) for name, lines in blocks if any(l.strip() for l in lines)]


def strip_comment_lines(code, cmt):
    return [line for line in code.splitlines() if line.strip() and not line.lstrip().startswith(cmt)]


def assigned_names(code, cmt):
    """Names assigned with := in GAP or Magma code (used to clear the namespace between groups)."""
    names = []
    for line in strip_comment_lines(code, cmt):
        for statement in line.split(";"):
            if ":=" not in statement:
                continue
            lhs = statement.split(":=")[0]
            for ident in IDENT_RE.findall(lhs):
                if ident not in GAP_MAGMA_KEYWORDS and ident not in names:
                    names.append(ident)
    return names


# ---------------------------------------------------------------------------
# Fetching the snippet files
# ---------------------------------------------------------------------------

class LocalFetcher:
    """Render the codedownload pages with the Flask test client of this LMFDB checkout."""

    def __init__(self):
        from lmfdb.app import app

        app.config["TESTING"] = True
        if not app.secret_key:
            app.secret_key = "test_secret_key_for_testing_only"
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        import lmfdb.website
        assert lmfdb.website
        from lmfdb import db
        for table in db.tablenames:
            db[table].slow_cutoff = 1e5
        from lmfdb.knowledge.knowl import knowldb
        knowldb.slow_cutoff = 1e5

    def get(self, label, lang):
        response = self.client.get(f"/Groups/Abstract/{label}/codedownload/{lang}")
        return response.status_code, response.get_data(as_text=True)


class RemoteFetcher:
    """Fetch the codedownload pages from a running LMFDB server (e.g. http://127.0.0.1:37777)."""

    def __init__(self, base_url, delay):
        self.base_url = base_url.rstrip("/")
        self.delay = delay

    def get(self, label, lang):
        import urllib.request
        import urllib.error

        time.sleep(self.delay)
        url = f"{self.base_url}/Groups/Abstract/{label}/codedownload/{lang}"
        request = urllib.request.Request(url, headers={"User-Agent": "lmfdb-check-group-snippets"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            return err.code, err.read().decode("utf-8", errors="replace")


def group_labels(args, cache_dir):
    if args.labels:
        labels = list(args.labels)
    elif args.offline:
        labels = [p.stem for p in cache_dir.glob("*.txt")]
    else:
        from lmfdb import db
        query = {}
        lo = label_key(args.start)[0] if args.start else args.min_order
        if lo or args.max_order:
            query["order"] = {}
            if lo:
                query["order"]["$gte"] = lo
            if args.max_order:
                query["order"]["$lte"] = args.max_order
        labels = list(db.gps_groups.search(query, "label"))

    bad = [l for l in labels if not GAP_LABEL_RE.match(l)]
    if args.labels and bad:
        sys.exit(f"Not GAP-style labels N.i: {', '.join(bad)}")
    labels = sorted((l for l in labels if GAP_LABEL_RE.match(l)), key=label_key)
    if args.start:
        labels = [l for l in labels if label_key(l) >= label_key(args.start)]
    if args.end:
        labels = [l for l in labels if label_key(l) <= label_key(args.end)]
    if args.min_order:
        labels = [l for l in labels if label_key(l)[0] >= args.min_order]
    if args.max_order:
        labels = [l for l in labels if label_key(l)[0] <= args.max_order]
    if args.limit:
        labels = labels[:args.limit]
    return labels


# ---------------------------------------------------------------------------
# CAS session
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, lang, args):
        self.lang = lang
        self.args = args
        self.cmt = gst.comment_dict[lang]
        self.prompt = gst.prompt_dict[lang]
        # Regexes for "statement finished" (index 0) and "statement unfinished" (index 1).
        # GAP's continuation prompt "> " is not preceded by a newline when the pty does not echo,
        # so match it at the start of the new output as well.
        continuation = gst.continuation_dict.get(lang)
        self.patterns = [re.compile(re.escape(self.prompt))]
        if lang == "gap":
            self.patterns.append(re.compile(r"(?:^|\n)(?:\x1b\[[0-9;]*m)*> "))
        elif continuation and continuation != self.prompt:
            self.patterns.append(re.compile(re.escape(continuation)))
        self.proc = None
        self.version = None
        self.groups_since_start = 0
        self.previous_names = []
        self.restarts = -1
        self.start()

    # -- process management ------------------------------------------------

    def start(self):
        self.close()
        print(f"[{self.lang}] starting session")
        self.proc = gst._start_snippet_procs([self.lang], chimp_spec=self.args.chimp_spec)[self.lang]
        self.child = self.proc.child
        if self.lang == "oscar":
            self.proc.run_command("import REPL; using Base64", timeout=300)
        if self.version is None:
            try:
                out = clean(self.proc.run_command(gst.version_cmd_dict[self.lang], timeout=120))
                self.version = next((l.strip() for l in out.splitlines() if l.strip()), "unknown")
            except Exception:
                self.version = "unknown"
        self.groups_since_start = 0
        self.previous_names = []
        self.restarts += 1

    def close(self):
        if self.proc is not None:
            try:
                self.child.terminate(force=True)
            except Exception:
                pass
            self.proc = None

    def recover(self):
        """Interrupt the running command and get back to a clean prompt, restarting if necessary."""
        try:
            self.child.sendintr()
            gst._resync(self.proc, self.lang, timeout=60)
        except Exception:
            print(f"[{self.lang}] could not resynchronise, restarting")
            self.start()

    def finish_statement(self):
        """Get out of an unfinished statement: try closing it with ';', otherwise interrupt."""
        if self.lang in ("gap", "magma"):
            try:
                self.child.sendline(";")
                self.child.expect(self.patterns[0], timeout=self.args.timeout)
                gst._resync(self.proc, self.lang, timeout=30)
                return
            except Exception:
                pass
        self.recover()

    def quiet(self, command, timeout=60):
        """Run a housekeeping command, ignoring its output."""
        try:
            self.child.sendline(command)
            self.child.expect_exact(self.prompt, timeout=timeout)
        except (pexpect.TIMEOUT, pexpect.EOF):
            self.start()

    # -- per group ---------------------------------------------------------

    def new_group(self):
        if self.lang in ("sage", "sage_gap"):
            self.quiet("reset()")
        elif self.lang == "oscar":
            self.quiet("lmfdb_snippet_module = Module(:LMFDBSnippet); Core.eval(lmfdb_snippet_module, :(using Oscar));",
                       timeout=300)
        elif self.lang == "gap" and self.previous_names:
            names = ", ".join(f'"{n}"' for n in self.previous_names)
            self.quiet(f"for lmfdb_snippet_name in [{names}] do if IsBoundGlobal(lmfdb_snippet_name) and "
                       f"not IsReadOnlyGlobal(lmfdb_snippet_name) then UnbindGlobal(lmfdb_snippet_name); fi; od;")
        elif self.lang == "magma":
            for name in self.previous_names:
                self.quiet(f"delete {name};")
        self.previous_names = []

    def run_block(self, code):
        """Return (status, output, seconds) for one snippet block."""
        if self.lang in ("gap", "magma"):
            for name in assigned_names(code, self.cmt):
                if name not in self.previous_names:
                    self.previous_names.append(name)

        if self.lang == "oscar":
            # Julia's REPL has no continuation prompt, so send the whole block as one
            # expression, evaluated in this group's module with REPL soft-scope rules.
            encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
            lines = [f'include_string(REPL.softscope, lmfdb_snippet_module, String(base64decode("{encoded}")))']
        else:
            lines = strip_comment_lines(code, self.cmt)

        output = []
        start = time.time()
        matched = 0
        for line in lines:
            self.child.sendline(line)
            try:
                matched = self.child.expect(self.patterns, timeout=self.args.timeout)
            except pexpect.TIMEOUT:
                output.append(self.child.before or "")
                self.recover()
                return "timeout", clean("".join(output)), time.time() - start
            except pexpect.EOF:
                output.append(self.child.before or "")
                self.start()
                return "crash", clean("".join(output)), time.time() - start
            output.append(self.child.before or "")

        status = None
        if matched == 1:  # block ended at a continuation prompt
            if self.lang in ("sage", "sage_gap"):
                # IPython needs a blank line to finish an indented block
                for _ in range(3):
                    self.child.sendline("")
                    try:
                        matched = self.child.expect(self.patterns, timeout=self.args.timeout)
                    except (pexpect.TIMEOUT, pexpect.EOF):
                        self.recover()
                        status = "timeout"
                        break
                    output.append(self.child.before or "")
                    if matched == 0:
                        break
            if matched == 1 and status is None:
                status = "incomplete"
                self.finish_statement()

        text = clean("".join(output))
        if status is None:
            if ERROR_RE[self.lang].search(text):
                status = "error"
            elif WARNING_RE[self.lang].search(text):
                status = "warning"
            else:
                status = "ok"
        return status, text, time.time() - start


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def check_group(session, label, text, args):
    blocks = parse_blocks(text, session.cmt)
    session.new_group()
    failures = []
    for index, (name, code) in enumerate(blocks):
        if any(s.lower() in name.lower() for s in args.skip_block):
            continue
        restarts = session.restarts
        status, output, seconds = session.run_block(code)
        if session.restarts != restarts and index > 0:
            # The CAS was restarted while running this block: define the group again, so the
            # remaining blocks are not reported as (spurious) consequential errors.
            session.run_block(blocks[0][1])
        if status == "ok" or (status == "warning" and args.ignore_warnings):
            continue
        failure = {"block": name, "status": status, "seconds": round(seconds, 2),
                   "code": code, "output": truncate(output.strip(), args.max_output)}
        failures.append(failure)
        if index == 0 and status in FAIL_STATUSES:
            failure["note"] = "group construction failed, remaining blocks not run"
            break
    if any(f["status"] in FAIL_STATUSES for f in failures):
        group_status = "fail"
    elif failures:
        group_status = "warning"
    else:
        group_status = "ok"
    return {"label": label, "status": group_status, "blocks": len(blocks), "failures": failures}


def read_results(path):
    records = {}
    if path.exists():
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    record = json.loads(line)
                    records[record["label"]] = record
    return records


def get_snippet_file(label, lang, cache_dir, args, fetcher_box):
    cached = cache_dir / f"{label}.txt"
    if cached.exists() and not args.refetch:
        return 200, cached.read_text()
    if args.offline:
        return None, "not in cache (running with --offline)"
    if fetcher_box[0] is None:
        fetcher_box[0] = RemoteFetcher(args.base_url, args.delay) if args.base_url else LocalFetcher()
    status, text = fetcher_box[0].get(label, lang)
    if status == 200:
        cached.write_text(text)
    return status, text


def run_language(lang, args):
    outdir = Path(args.outdir) / lang
    cache_dir = outdir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    results_path = outdir / "results.jsonl"
    meta_path = outdir / "meta.json"

    if args.summary_only:
        write_summary(lang, outdir)
        return

    done = set(read_results(results_path)) if args.resume else set()
    if not args.resume and results_path.exists():
        results_path.unlink()

    labels = group_labels(args, cache_dir)
    todo = [l for l in labels if l not in done]
    print(f"[{lang}] {len(labels)} groups selected, {len(todo)} to check"
          + (f" ({todo[0]} .. {todo[-1]})" if todo else ""))
    if not todo:
        write_summary(lang, outdir)
        return

    session = Session(lang, args)
    meta = {"lang": lang, "version": session.version, "started": datetime.datetime.now().isoformat(timespec="seconds"),
            "command": " ".join(sys.argv)}
    meta_path.write_text(json.dumps(meta, indent=2))
    fetcher_box = [None]

    try:
        with results_path.open("a") as results:
            for count, label in enumerate(todo, 1):
                status, text = get_snippet_file(label, lang, cache_dir, args, fetcher_box)
                start = time.time()
                if status != 200:
                    record = {"label": label, "status": "fetch_error", "blocks": 0,
                              "failures": [{"block": "(download)", "status": f"HTTP {status}" if status else "not cached",
                                            "code": "", "output": truncate(clean(text).strip(), 1000)}]}
                else:
                    record = check_group(session, label, text, args)
                record["seconds"] = round(time.time() - start, 2)
                results.write(json.dumps(record) + "\n")
                results.flush()

                prefix = f"[{lang}] ({count}/{len(todo)}) {label}"
                if record["status"] == "ok":
                    if not args.quiet:
                        print(f"{prefix}: ok ({record['blocks']} blocks, {record['seconds']}s)")
                else:
                    detail = "; ".join(f"{f['block']} [{f['status']}]" for f in record["failures"])
                    print(f"{prefix}: {record['status'].upper()}: {detail}")

                session.groups_since_start += 1
                if args.restart_every and session.groups_since_start >= args.restart_every:
                    session.start()
    except KeyboardInterrupt:
        print(f"\n[{lang}] interrupted; rerun with --resume to continue")
    finally:
        session.close()
        write_summary(lang, outdir)


def error_signature(output, lang):
    """A short description of the first error (or warning) in some CAS output, used to group failures."""
    lines = [l.strip() for l in output.splitlines()]
    for regex in (ERROR_RE[lang], WARNING_RE[lang]):
        for i, line in enumerate(lines):
            if regex.search(line) and not line.startswith(">>"):
                signature = line
                if i + 1 < len(lines) and lines[i + 1].startswith("Argument types given"):
                    signature += " / " + lines[i + 1]
                return signature[:200]
    return next((l for l in lines if l and not l.startswith(">>")), "(no output)")[:200]


def construction_of(label, lang, outdir, cache={}):
    """The group-defining snippet (first block) of a cached codedownload file."""
    if (label, lang) not in cache:
        path = outdir / "cache" / f"{label}.txt"
        blocks = parse_blocks(path.read_text(), gst.comment_dict[lang]) if path.exists() else []
        cache[label, lang] = blocks[0][1] if blocks else "(not cached)"
    return cache[label, lang]


def normalise_construction(code):
    """Replace the numbers in a construction by N, so e.g. all DicyclicGroup(n) constructions compare equal."""
    first = next((l for l in code.splitlines() if l.strip()), "")
    return re.sub(r"\d+", "N", first.strip())[:150]


def write_summary(lang, outdir):
    records = sorted(read_results(outdir / "results.jsonl").values(),
                     key=lambda r: label_key(r["label"]) if GAP_LABEL_RE.match(r["label"]) else (0, 0))
    meta_path = outdir / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    statuses = Counter(r["status"] for r in records)

    by_block = defaultdict(list)
    by_construction = defaultdict(lambda: {"labels": [], "blocks": Counter()})
    for record in records:
        if not record["failures"]:
            continue
        for failure in record["failures"]:
            by_block[(failure["block"], failure["status"])].append((record["label"], failure))
        if record["status"] != "fetch_error":
            key = normalise_construction(construction_of(record["label"], lang, outdir))
            by_construction[key]["labels"].append(record["label"])
            by_construction[key]["blocks"].update(f["block"] for f in record["failures"])
    ordered = sorted(by_block.items(), key=lambda item: (item[0][1] == "warning", -len(item[1]), item[0][0]))

    def label_list(labels, limit):
        return ", ".join(labels[:limit]) + (", ..." if len(labels) > limit else "")

    lines = [f"# Abstract group snippet check: {lang}", ""]
    lines.append(f"- CAS version: {meta.get('version', 'unknown')}")
    lines.append(f"- Run started: {meta.get('started', '?')}; summary written {datetime.datetime.now().isoformat(timespec='seconds')}")
    if records:
        lines.append(f"- Groups checked: {len(records)} ({records[0]['label']} .. {records[-1]['label']})")
    lines.append("- " + ", ".join(f"{k}: {v}" for k, v in sorted(statuses.items())))
    lines.append("")

    if not ordered:
        lines.append("No failing snippets.")
    else:
        lines += ["## Failing groups by construction", "",
                  "Groups whose snippets fail, grouped by the snippet that defines G (numbers replaced by N).", "",
                  "| Construction | Groups | Failing blocks | Labels |", "|---|---|---|---|"]
        for key, info in sorted(by_construction.items(), key=lambda item: -len(item[1]["labels"])):
            blocks = len(info["blocks"])
            lines.append(f"| `{key}` | {len(info['labels'])} | {blocks} | {label_list(info['labels'], 10)} |")
        lines += ["", "## Failing blocks", "", "| Snippet | Status | Groups | Distinct errors | First groups |",
                  "|---|---|---|---|---|"]
        details = []
        for (block, status), items in ordered:
            by_signature = defaultdict(list)
            for label, failure in items:
                by_signature[error_signature(failure["output"], lang)].append((label, failure))
            lines.append(f"| {block} | {status} | {len(items)} | {len(by_signature)} | "
                         f"{label_list([l for l, _ in items], 8)} |")

            details += [f"### {block} ({status}, {len(items)} groups)", ""]
            for signature, group_items in sorted(by_signature.items(), key=lambda item: -len(item[1])):
                label, failure = group_items[0]
                details += [f"**{signature}** ({len(group_items)} groups): {label_list([l for l, _ in group_items], 40)}", "",
                            f"Example {label}, with G defined by `{construction_of(label, lang, outdir).strip()}`:", "",
                            "```", failure["code"], "```", "", "```", truncate(failure["output"], 2000), "```", ""]
        lines += [""] + details

    summary_path = outdir / "summary.md"
    summary_path.write_text("\n".join(lines) + "\n")
    print(f"[{lang}] {', '.join(f'{k}: {v}' for k, v in sorted(statuses.items())) or 'no results'}; summary in {summary_path}")
    for (block, status), items in ordered[:15]:
        print(f"    {len(items):6d}  {status:10s} {block}")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the code snippets of all LMFDB abstract groups and report failures.")
    parser.add_argument("-l", "--langs", nargs="+", choices=LANGS, default=["magma", "gap", "sage", "oscar"],
                        help="languages to check (default: magma gap sage oscar); run one process per language to parallelise")
    parser.add_argument("--start", help="first group label, e.g. 64.1")
    parser.add_argument("--end", help="last group label (inclusive)")
    parser.add_argument("--min-order", type=int, default=None)
    parser.add_argument("--max-order", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None, help="check at most this many groups")
    parser.add_argument("--labels", nargs="+", help="check exactly these groups instead of querying the database")
    parser.add_argument("--base-url", help="fetch snippets from this server (e.g. http://127.0.0.1:37777) instead of the "
                                           "Flask test client of this checkout")
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to wait between requests with --base-url")
    parser.add_argument("--offline", action="store_true", help="only use cached snippet files (no database or server needed)")
    parser.add_argument("--refetch", action="store_true", help="download snippet files again even if cached")
    parser.add_argument("--outdir", default="snippet_check", help="output directory (default: snippet_check)")
    parser.add_argument("--resume", action="store_true", help="skip groups already in results.jsonl")
    parser.add_argument("--summary-only", action="store_true", help="only rewrite summary.md from results.jsonl")
    parser.add_argument("--timeout", type=float, default=120, help="seconds allowed per line (per block for Oscar)")
    parser.add_argument("--restart-every", type=int, default=250, help="restart the CAS every N groups (0 = never)")
    parser.add_argument("--skip-block", action="append", default=[], metavar="TEXT",
                        help="skip blocks whose description contains TEXT (case-insensitive), e.g. 'subgroups'; repeatable")
    parser.add_argument("--ignore-warnings", action="store_true", help="do not report blocks that only print warnings")
    parser.add_argument("--max-output", type=int, default=4000, help="characters of output kept per failure")
    parser.add_argument("--cmd", action="append", default=[], metavar="LANG=COMMAND",
                        help="override the command used to start a CAS, e.g. --cmd 'gap=gap -b -T -r'")
    parser.add_argument("-c", "--chimp", help="path to CHIMP (or CHIMP.spec) for Magma; defaults to $CHIMP_SPEC",
                        default=os.environ.get("CHIMP_SPEC"))
    parser.add_argument("-q", "--quiet", action="store_true", help="only print failing groups")
    args = parser.parse_args()

    for item in args.cmd:
        lang, _, command = item.partition("=")
        if lang not in gst.exec_dict or not command:
            parser.error(f"bad --cmd {item!r}")
        gst.exec_dict[lang] = command

    args.chimp_spec = None
    if args.chimp and "magma" in args.langs:
        chimp = Path(args.chimp).expanduser()
        if chimp.is_dir():
            chimp = chimp / "CHIMP.spec"
        if not chimp.exists():
            parser.error(f"could not find CHIMP spec at {chimp}")
        args.chimp_spec = str(chimp.resolve())
    for label in (args.start, args.end):
        if label and not GAP_LABEL_RE.match(label):
            parser.error(f"{label} is not a label of the form N.i")
    return args


def main():
    args = parse_args()
    for lang in args.langs:
        run_language(lang, args)


if __name__ == "__main__":
    main()
