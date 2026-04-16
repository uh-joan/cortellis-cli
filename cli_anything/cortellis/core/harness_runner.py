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


def _resolve_vars(text: str, state: dict[str, NodeResult]) -> str:
    """Replace $node_id.output references with captured stdout from that node."""
    def replacer(m):
        node_id = m.group(1)
        rest = m.group(2)  # e.g. ".indication_id" or ""
        result = state.get(node_id)
        if result is None:
            return m.group(0)
        output = result.output.strip()
        # Simple field extraction: if output is "id,name" and rest is ".indication_id"
        if rest == ".indication_id" and "," in output:
            return output.split(",", 1)[0]
        if rest == ".indication_name" and "," in output:
            return output.split(",", 1)[1]
        if rest in (".output.status", ".output"):
            return output
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
    """Return True if this node should be skipped (when: false or upstream failed)."""
    # Check trigger_rule first
    if node.trigger_rule == "all_success":
        for dep in node.depends_on:
            dep_result = state.get(dep)
            if dep_result and dep_result.status == "failed":
                return True

    # trigger_rule == all_done: run if all upstreams done (success OR skipped)
    # but skip if when: condition is false
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


def _exec_node(node: Node, bash: str, output_dir: Path) -> NodeResult:
    """Run the resolved bash command and return a NodeResult."""
    t0 = time.monotonic()
    result = subprocess.run(
        bash,
        shell=True,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    duration = time.monotonic() - t0
    status = "success" if result.returncode == 0 else ("failed" if not node.allow_fail else "success")
    if result.returncode != 0:
        print(f"  [{node.id}] stderr: {result.stderr.strip()[:300]}", file=sys.stderr)
        if not node.allow_fail:
            status = "failed"
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

        # Seed ARGUMENTS variable (used in bash templates)
        def resolve(text: str) -> str:
            t = text.replace("$ARGUMENTS", indication)
            return _resolve_vars(t, state)

        for wave_idx, wave in enumerate(self.waves):
            wave_label = " ".join(n.id for n in wave)
            print(f"\n▶ Wave {wave_idx}: {wave_label}", file=sys.stderr, flush=True)

            # Determine which nodes in this wave actually run
            to_run: list[Node] = []
            for node in wave:
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
