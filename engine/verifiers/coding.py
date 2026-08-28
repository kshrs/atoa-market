"""
Coding Verifier Module (CodeValidatorBot).
Executes, benchmarks, and validates submitted code in an isolated sandbox with timeout,
cross-platform process-tree cleanup, and AST security checks.
"""
import ast
import asyncio
import os
import signal
import subprocess
import sys
import tempfile
import time
from typing import Dict, Any, Tuple
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult


FORBIDDEN_AST_MODULES = {"ctypes", "winreg", "_winapi", "pty"}
FORBIDDEN_FUNCS = {"eval", "exec", "__import__"}


def _check_ast_safety(code: str, allow_subprocess: bool = False) -> Tuple[bool, str]:
    """
    Perform static AST inspection to block dangerous syscalls, dynamic code evaluation,
    introspection chains, and forbidden modules.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

    for node in ast.walk(tree):
        # 1. Check static imports
        if isinstance(node, ast.Import):
            for name in node.names:
                root_pkg = name.name.split('.')[0]
                if root_pkg in FORBIDDEN_AST_MODULES:
                    return False, f"SecurityViolation: Import of forbidden module '{root_pkg}'"
                if not allow_subprocess and root_pkg == "subprocess":
                    return False, "SecurityViolation: Subprocess execution not permitted in submitted solution"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_pkg = node.module.split('.')[0]
                if root_pkg in FORBIDDEN_AST_MODULES:
                    return False, f"SecurityViolation: Import from forbidden module '{root_pkg}'"
                if not allow_subprocess and root_pkg == "subprocess":
                    return False, "SecurityViolation: Subprocess execution not permitted in submitted solution"

        # 2. Check dynamic execution functions (eval, exec, __import__)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_FUNCS:
                return False, f"SecurityViolation: Use of dynamic execution function '{node.func.id}'"
            elif isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_FUNCS:
                return False, f"SecurityViolation: Use of dynamic execution function '{node.func.attr}'"

        # 3. Check gadget chain attributes (__subclasses__)
        elif isinstance(node, ast.Attribute):
            if node.attr == "__subclasses__":
                return False, "SecurityViolation: Introspection of __subclasses__ is forbidden"

    return True, "AST inspection passed"


def _terminate_process_tree(proc: asyncio.subprocess.Process) -> None:
    """
    Cross-platform process-tree termination to avoid orphaned child processes on timeout.
    """
    if proc.returncode is not None:
        return

    pid = proc.pid
    if not pid:
        return

    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                timeout=2,
                check=False
            )
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    else:
        # POSIX process group termination
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


async def verify_coding(task_spec: TaskManifest, deliverable: DeliverablePayload) -> EvaluationResult:
    """
    Evaluates submitted code deliverable against task manifest requirements and test suite.
    """
    task_id = task_spec.task_id
    code = deliverable.submitted_code or deliverable.submitted_files.get("solution.py", "")
    test_code = task_spec.test_suite or deliverable.submitted_files.get("test_solution.py", "")
    
    proof_logs = []
    benchmark_metrics: Dict[str, Any] = {
        "syntax_valid": False,
        "ast_safe": False,
        "tests_passed": 0,
        "total_tests": 0,
        "execution_time_ms": 0.0,
        "timed_out": False,
        "returncode": None,
        "failure_category": "NONE",
    }

    if not code.strip():
        benchmark_metrics["failure_category"] = "EMPTY_PAYLOAD"
        return EvaluationResult(
            task_id=task_id,
            verdict="FAIL",
            score=0.0,
            slashing_recommended=True,
            benchmark_metrics=benchmark_metrics,
            proof_logs="FAIL: No code provided in deliverable.",
            details={"error": "Empty code deliverable"}
        )

    # 1. AST Syntax & Security Check
    is_safe, safety_msg = _check_ast_safety(
        code, 
        allow_subprocess=task_spec.constraints.get("allow_subprocess", False)
    )
    proof_logs.append(f"[AST Check] {safety_msg}")

    if not is_safe:
        benchmark_metrics["ast_safe"] = False
        is_malicious = "SecurityViolation" in safety_msg
        benchmark_metrics["failure_category"] = "SECURITY_VIOLATION" if is_malicious else "SYNTAX_ERROR"
        return EvaluationResult(
            task_id=task_id,
            verdict="FAIL",
            score=0.0,
            slashing_recommended=is_malicious,
            benchmark_metrics=benchmark_metrics,
            proof_logs="\n".join(proof_logs),
            details={"error": safety_msg}
        )

    benchmark_metrics["syntax_valid"] = True
    benchmark_metrics["ast_safe"] = True

    # 2. Subprocess Sandbox Execution
    timeout_sec = float(task_spec.constraints.get("timeout_sec", task_spec.constraints.get("timeout_seconds", 5.0)))
    max_latency_ms = task_spec.constraints.get("max_latency_ms", None)

    with tempfile.TemporaryDirectory() as sandbox_dir:
        solution_path = os.path.join(sandbox_dir, "solution.py")
        with open(solution_path, "w", encoding="utf-8") as f:
            f.write(code)

        for fname, content in deliverable.submitted_files.items():
            if fname != "solution.py":
                fpath = os.path.join(sandbox_dir, fname)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

        test_path = os.path.join(sandbox_dir, "test_solution.py")
        if test_code.strip():
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_code)
            cmd = [sys.executable, "-m", "pytest", "-v", "test_solution.py"]
        else:
            cmd = [sys.executable, "solution.py"]

        start_time = time.perf_counter()
        try:
            clean_env = os.environ.copy()
            clean_env["PYTHONPATH"] = sandbox_dir
            clean_env["PYTHONDONTWRITEBYTECODE"] = "1"
            clean_env["PYTHONHASHSEED"] = "0"

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=sandbox_dir,
                env=clean_env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), 
                    timeout=timeout_sec
                )
                exec_time_ms = (time.perf_counter() - start_time) * 1000.0
                stdout_str = stdout_bytes.decode("utf-8", errors="replace")
                stderr_str = stderr_bytes.decode("utf-8", errors="replace")
                returncode = proc.returncode
            except asyncio.TimeoutError:
                _terminate_process_tree(proc)
                await proc.wait()
                benchmark_metrics["timed_out"] = True
                benchmark_metrics["failure_category"] = "TIMEOUT"
                benchmark_metrics["execution_time_ms"] = timeout_sec * 1000.0
                proof_logs.append(f"[Execution Cap] Process timed out after {timeout_sec}s and process tree was terminated.")
                return EvaluationResult(
                    task_id=task_id,
                    verdict="FAIL",
                    score=0.0,
                    slashing_recommended=True,
                    benchmark_metrics=benchmark_metrics,
                    proof_logs="\n".join(proof_logs),
                    details={"error": f"Execution timed out ({timeout_sec}s cap)"}
                )

        except Exception as ex:
            benchmark_metrics["failure_category"] = "EXECUTION_ERROR"
            proof_logs.append(f"[Execution Error] {str(ex)}")
            return EvaluationResult(
                task_id=task_id,
                verdict="FAIL",
                score=0.0,
                slashing_recommended=True,
                benchmark_metrics=benchmark_metrics,
                proof_logs="\n".join(proof_logs),
                details={"error": str(ex)}
            )

    benchmark_metrics["execution_time_ms"] = round(exec_time_ms, 2)
    benchmark_metrics["returncode"] = returncode
    proof_logs.append(f"[Execution Output]\nSTDOUT:\n{stdout_str}\nSTDERR:\n{stderr_str}")

    score = 0.0
    if returncode == 0:
        score = 1.0
        if max_latency_ms and exec_time_ms > max_latency_ms:
            proof_logs.append(f"[Latency Alert] Exec time {exec_time_ms:.2f}ms exceeds target {max_latency_ms}ms")
            latency_factor = max(0.5, max_latency_ms / exec_time_ms)
            score = score * latency_factor
    else:
        benchmark_metrics["failure_category"] = "TEST_FAILURE"
        import re
        passed_m = re.search(r"(\d+) passed", stdout_str)
        failed_m = re.search(r"(\d+) failed", stdout_str)
        p_count = int(passed_m.group(1)) if passed_m else 0
        f_count = int(failed_m.group(1)) if failed_m else 0
        tot = p_count + f_count
        benchmark_metrics["tests_passed"] = p_count
        benchmark_metrics["total_tests"] = tot
        if tot > 0:
            score = p_count / tot

    verdict: "Literal['PASS', 'FAIL']" = "PASS" if score >= task_spec.passing_threshold else "FAIL"
    if verdict == "PASS":
        benchmark_metrics["failure_category"] = "NONE"
    slashing = score < task_spec.slashing_threshold

    return EvaluationResult(
        task_id=task_id,
        verdict=verdict,
        score=round(score, 4),
        slashing_recommended=slashing,
        benchmark_metrics=benchmark_metrics,
        proof_logs="\n".join(proof_logs),
        details={"stdout": stdout_str, "stderr": stderr_str, "returncode": returncode}
    )
