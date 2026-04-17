"""Pharma intelligence harness — wave-based DAG executor for workflow.yaml.

Reads a workflow YAML DAG and executes recipe nodes with:
- Topological wave scheduling (graphlib.TopologicalSorter)
- Parallel fetch execution via ThreadPoolExecutor
- API rate-limit semaphore (max 3 concurrent Cortellis API calls)
- Per-directory filesystem mutex for nodes that write shared output dirs
- 3-state node lifecycle: success | skipped | failed
- when: condition evaluation + trigger_rule: all_done support
- Resume: skip nodes whose output file already exists
- Review gate before compile node
"""

import re
import shlex
import subprocess
import sys
import threading
import time
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from graphlib import TopologicalSorter
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]

# Max simultaneous Cortellis API calls — 3 is safe; 6 causes 429s under pagination load
_API_SEM = threading.Semaphore(3)

# Per-output-dir filesystem locks — prevents concurrent writes to same raw/ directory
_FS_LOCKS: dict[str, threading.Lock] = {}
_FS_LOCKS_MUTEX = threading.Lock()


def _get_fs_lock(output_dir: str) -> threading.Lock:
    with _FS_LOCKS_MUTEX:
        if output_dir not in _FS_LOCKS:
            _FS_LOCKS[output_dir] = threading.Lock()
        return _FS_LOCKS[output_dir]


@dataclass
class Node:
    id: str
    bash: str
    depends_on: list[str] = field(default_factory=list)
    when: Optional[str] = None
    trigger_rule: str = "all_success"   # all_success | all_done
    model: str = "sonnet"
    api_calls: bool = False
    fs_exclusive: bool = False
    allow_fail: bool = False
    review_gate: bool = False
    resume_output: Optional[str] = None  # if set, skip if this file exists


@dataclass
class NodeResult:
    status: str   # success | skipped | failed
    output: str = ""
    returncode: int = 0
    duration: float = 0.0


def _load_nodes(yaml_path: Path) -> list[Node]:
    with open(yaml_path) as f:
        doc = yaml.safe_load(f)
    nodes = []
    for n in doc.get("nodes", []):
        nodes.append(Node(
            id=n["id"],
            bash=n.get("bash", ""),
            depends_on=n.get("depends_on", []),
            when=n.get("when"),
            trigger_rule=n.get("trigger_rule", "all_success"),
            model=n.get("model", "sonnet"),
            api_calls=n.get("api_calls", False),
            fs_exclusive=n.get("fs_exclusive", False),
            allow_fail=n.get("allow_fail", False),
            review_gate=n.get("review_gate", False),
            resume_output=n.get("resume_output"),
        ))
    return nodes


def _plan_waves(nodes: list[Node]) -> list[list[Node]]:
    """Group nodes into topological waves — nodes in the same wave are independent."""
    by_id = {n.id: n for n in nodes}
    ts = TopologicalSorter({n.id: set(n.depends_on) for n in nodes})
    ts.prepare()
    waves = []
    while ts.is_active():
        ready_ids = list(ts.get_ready())
        if not ready_ids:
            break
        wave = [by_id[nid] for nid in ready_ids]
        waves.append(wave)
        for nid in ready_ids:
            ts.done(nid)
    return waves


def _slug_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _resolve_vars(text: str, state: dict[str, NodeResult]) -> str:
    """Replace $node_id.output references with captured stdout from that node.

    CSV field aliases (resolve nodes output comma-separated values):
      field 0: indication_id, company_id, drug_id, target_id  → raw
      field 1: indication_name, company_name, drug_name,
               target_name, conference_name, comparison_name  → slugified
               *_canonical                                    → raw
      field 2: active_drugs, drug_phase, gene_symbol          → raw
      field 3+: action_name (join_remaining=True)             → raw joined
      field 4: inn_slug                                       → raw
    """
    # Maps suffix → (csv_index, slugify[, join_remaining])
    _FIELD_MAP: dict[str, tuple] = {
        # Indication / landscape
        ".output.indication_id":        (0, False),
        ".output.indication_name":      (1, True),
        ".output.indication_canonical": (1, False),
        # Company / pipeline
        ".output.company_id":           (0, False),
        ".output.company_name":         (1, True),
        ".output.company_slug":         (1, True),
        ".output.company_canonical":    (1, False),
        ".output.active_drugs":         (2, False),
        # Drug-profile (resolve_drug.py: drug_id,drug_name,phase,indication_count,inn_slug)
        ".output.drug_id":              (0, False),
        ".output.drug_name":            (1, True),
        ".output.drug_canonical":       (1, False),
        ".output.drug_phase":           (2, False),
        ".output.inn_slug":             (4, False),
        # Target-profile (resolve_target_id.py: target_id,target_name,gene_symbol,action_name)
        ".output.target_id":            (0, False),
        ".output.target_name":          (1, True),
        ".output.target_canonical":     (1, False),
        ".output.gene_symbol":          (2, False),
        ".output.action_name":          (3, False, True),  # join fields 3+ (action may have commas)
        # Generic slug for conference, comparison, changelog (field 1 slugified)
        ".output.conference_name":      (1, True),
        ".output.comparison_name":      (1, True),
        # Fallbacks
        ".output.status":               (-1, False),
        ".output":                      (-1, False),
    }

    def replacer(m):
        node_id = m.group(1)
        rest = m.group(2) or ""
        result = state.get(node_id)
        if result is None:
            return m.group(0)
        output = result.output.strip()

        if rest in _FIELD_MAP:
            entry = _FIELD_MAP[rest]
            idx, do_slug = entry[0], entry[1]
            join_remaining = entry[2] if len(entry) > 2 else False
            if idx == -1:
                return output
            parts = output.split(",")
            if join_remaining:
                val = ",".join(parts[idx:]) if len(parts) > idx else ""
            elif idx < len(parts):
                val = parts[idx]
            else:
                return output
            return _slug_name(val) if do_slug else val

        return output

    return re.sub(r'\$([a-z_][a-z0-9_]*)(\.[a-z_.]+)?', replacer, text)


def _eval_when(condition: str, state: dict[str, NodeResult]) -> bool:
    """Evaluate a when: condition string. Returns True if node SHOULD run."""
    resolved = _resolve_vars(condition, state)
    # Handle: "value != 'fresh'" or "value == 'fresh'"
    m = re.match(r"^(.+?)\s*(!=|==)\s*'([^']*)'$", resolved.strip())
    if m:
        lhs, op, rhs = m.group(1).strip(), m.group(2), m.group(3)
        if op == "!=":
            return lhs != rhs
        if op == "==":
            return lhs == rhs
    # Fallback: truthy string
    return bool(resolved.strip())


def _should_skip(node: Node, state: dict[str, NodeResult]) -> bool:
    """Return True if this node should be skipped (when: false or upstream propagation)."""
    dep_results = [state[dep] for dep in node.depends_on if dep in state]

    if node.trigger_rule == "all_success":
        # Skip if any upstream failed OR skipped (propagate skip downstream)
        for r in dep_results:
            if r.status in ("failed", "skipped"):
                return True
    elif node.trigger_rule == "all_done":
        # Skip only when ALL upstreams are skipped (nothing was fetched — fresh path)
        if dep_results and all(r.status == "skipped" for r in dep_results):
            return True

    # Evaluate when: condition
    if node.when:
        return not _eval_when(node.when, state)

    return False


def _prompt_approval(report_path: Path) -> bool:
    print(f"\n── Review gate ─────────────────────────────────────────────", file=sys.stderr)
    print(f"  Report: {report_path}", file=sys.stderr)
    print(f"  Approve wiki compilation? [y/N] ", end="", file=sys.stderr, flush=True)
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "n"
    return answer in ("y", "yes")


_NODE_TIMEOUT = 600  # seconds; a hung recipe blocks its wave thread indefinitely


def _exec_node(node: Node, bash: str, output_dir: Path) -> NodeResult:
    """Run the resolved bash command and return a NodeResult."""
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            bash,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=_NODE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        print(f"  [{node.id}] TIMEOUT after {_NODE_TIMEOUT}s", file=sys.stderr)
        return NodeResult(status="failed", returncode=-1, duration=duration)
    duration = time.monotonic() - t0
    if result.returncode != 0:
        print(f"  [{node.id}] stderr: {result.stderr.strip()[:300]}", file=sys.stderr)
    status = "success" if result.returncode == 0 or node.allow_fail else "failed"
    return NodeResult(
        status=status,
        output=result.stdout,
        returncode=result.returncode,
        duration=duration,
    )


def _run_node(node: Node, bash: str, output_dir: Path) -> NodeResult:
    """Dispatch a single node with appropriate locking."""
    api_ctx = _API_SEM if node.api_calls else nullcontext()
    fs_ctx = _get_fs_lock(str(output_dir)) if node.fs_exclusive else nullcontext()

    with api_ctx:
        with fs_ctx:
            return _exec_node(node, bash, output_dir)


class HarnessRunner:
    def __init__(self, workflow_yaml: Path):
        self.nodes = _load_nodes(workflow_yaml)
        self.waves = _plan_waves(self.nodes)
        self._by_id = {n.id: n for n in self.nodes}

    def dry_run(self) -> None:
        """Print wave schedule without executing."""
        print(f"\n{'Wave':<6} {'Node':<25} {'When':<35} {'api_calls':<10} {'fs_exclusive'}")
        print("-" * 85)
        for i, wave in enumerate(self.waves):
            for node in wave:
                when = (node.when or "")[:33]
                print(f"{i:<6} {node.id:<25} {when:<35} {str(node.api_calls):<10} {node.fs_exclusive}")
        print()

    def execute(
        self,
        indication: str,
        output_dir: Path,
        *,
        dry_run: bool = False,
        force_refresh: bool = False,
        review: bool = False,
    ) -> int:
        """Run the full harness. Returns exit code (0=success, 1=failed, 2=review rejected)."""
        if dry_run:
            self.dry_run()
            return 0

        output_dir.mkdir(parents=True, exist_ok=True)
        state: dict[str, NodeResult] = {}

        # force_refresh: pre-seed freshness as 'stale' so all fetch nodes run
        # (bypasses the when: freshness != 'fresh' guards without touching the YAML)
        if force_refresh:
            state["freshness"] = NodeResult(status="success", output="stale")

        # Seed ARGUMENTS variable and pin python3 to the active venv interpreter
        python_bin = sys.executable
        def resolve(text: str) -> str:
            t = text.replace("$ARGUMENTS", shlex.quote(indication))
            t = re.sub(r'\bpython3\b', python_bin, t)
            return _resolve_vars(t, state)

        for wave_idx, wave in enumerate(self.waves):
            # After resolve completes, pin output_dir to the canonical slug
            # (resolve outputs "id,name" or "id,name,active_drugs,..." — field 1 is name)
            if wave_idx > 0 and "resolve" in state:
                r = state["resolve"]
                if r.status == "success":
                    parts = r.output.strip().split(",")
                    if len(parts) >= 2:
                        output_dir = output_dir.parent / _slug_name(parts[1])
                        output_dir.mkdir(parents=True, exist_ok=True)
            wave_label = " ".join(n.id for n in wave)
            print(f"\n▶ Wave {wave_idx}: {wave_label}", file=sys.stderr, flush=True)

            # Determine which nodes in this wave actually run
            to_run: list[Node] = []
            for node in wave:
                # Pre-seeded state (e.g. freshness overridden by force_refresh)
                if node.id in state:
                    self._log_result(node, state[node.id])
                    continue

                if _should_skip(node, state):
                    print(f"  [{node.id}] SKIPPED (when/trigger)", file=sys.stderr)
                    state[node.id] = NodeResult(status="skipped")
                    continue

                # Resume: skip if output file already present and not force_refresh
                if node.resume_output and not force_refresh:
                    out_file = output_dir / node.resume_output
                    if out_file.exists():
                        print(f"  [{node.id}] SKIPPED (resume — {out_file.name} exists)", file=sys.stderr)
                        state[node.id] = NodeResult(status="skipped")
                        continue

                # Review gate before compile
                if node.review_gate and review:
                    report_path = output_dir / "report.md"
                    if not _prompt_approval(report_path):
                        print(f"  [{node.id}] Review rejected — aborting.", file=sys.stderr)
                        return 2

                to_run.append(node)

            if not to_run:
                continue

            # Dispatch wave — parallel for independent nodes
            if len(to_run) == 1:
                node = to_run[0]
                bash = resolve(node.bash)
                print(f"  [{node.id}] running...", file=sys.stderr)
                result = _run_node(node, bash, output_dir)
                state[node.id] = result
                self._log_result(node, result)
                if result.status == "success" and result.output.strip() and node.id in ("read_wiki", "report"):
                    print(result.output, flush=True)
            else:
                futures = {}
                with ThreadPoolExecutor(max_workers=min(6, len(to_run))) as pool:
                    for node in to_run:
                        bash = resolve(node.bash)
                        print(f"  [{node.id}] dispatching...", file=sys.stderr)
                        fut = pool.submit(_run_node, node, bash, output_dir)
                        futures[fut] = node

                    for fut in as_completed(futures):
                        node = futures[fut]
                        try:
                            result = fut.result()
                        except Exception as exc:
                            result = NodeResult(status="failed", output=str(exc))
                        state[node.id] = result
                        self._log_result(node, result)
                        # Print terminal-output nodes directly to stdout
                        if result.status == "success" and result.output.strip() and node.id in ("read_wiki", "report"):
                            print(result.output, flush=True)

            # Check for hard failures (non-allow_fail nodes)
            for node in to_run:
                r = state.get(node.id)
                if r and r.status == "failed" and not node.allow_fail:
                    print(f"\n  HARNESS FAILED at node [{node.id}]", file=sys.stderr)
                    return 1

        return 0

    def _log_result(self, node: Node, result: NodeResult) -> None:
        icon = {"success": "✓", "skipped": "–", "failed": "✗"}.get(result.status, "?")
        print(f"  {icon} [{node.id}] {result.status} ({result.duration:.1f}s)", file=sys.stderr)
