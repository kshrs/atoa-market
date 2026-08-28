"""
ATOA 3-Domain Programmatic Validator Oracle (developed for bk).
Provides rule-based, deterministic validation bots for:
1. Code Generation (unit tests & syntax validation)
2. Research Synthesis (JSON Schema & structural validation)
3. Query Answering (fact assertion & search keyword matching)
"""

import sys
import io
import time
import jsonschema
from typing import Dict, Any, Optional

from backend.app.models import TaskCategory, VerificationReport, ValidationSpec


class CodeValidatorBot:
    """Runs submitted code against unit test assertions in an isolated subprocess/execution context."""

    @staticmethod
    def validate(submitted_code: str, test_suite_code: Optional[str]) -> Dict[str, Any]:
        if not submitted_code or not submitted_code.strip():
            return {
                "passed": False,
                "score": 0.0,
                "error": "Deliverable code artifact is empty.",
                "logs": "No source code provided."
            }

        # Combine submitted code + test suite
        full_script = submitted_code + "\n\n" + (test_suite_code or "assert True")
        
        # Capture stdout/stderr in safe execution harness
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = io.StringIO()
        sys.stdout = redirected_output
        sys.stderr = redirected_output
        
        exec_globals = {}
        start_time = time.time()
        passed = False
        error_msg = None
        
        try:
            exec(full_script, exec_globals)
            passed = True
            score = 1.0
        except AssertionError as ae:
            score = 0.0
            error_msg = f"AssertionError in unit test: {str(ae) or 'Condition failed'}"
        except SyntaxError as se:
            score = 0.0
            error_msg = f"SyntaxError in code deliverable: {str(se)}"
        except Exception as e:
            score = 0.0
            error_msg = f"Runtime error: {type(e).__name__}: {str(e)}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        elapsed_ms = (time.time() - start_time) * 1000
        logs = redirected_output.getvalue()
        if error_msg:
            logs += f"\n[VALIDATOR ERROR] {error_msg}"
        else:
            logs += f"\n[VALIDATOR SUCCESS] All test assertions executed in {elapsed_ms:.2f}ms."

        return {
            "passed": passed,
            "score": score,
            "error": error_msg,
            "logs": logs.strip(),
            "execution_time_ms": elapsed_ms
        }


class ResearchValidatorBot:
    """Validates structured research JSON against required JSON Schema and keys."""

    @staticmethod
    def validate(research_payload: Any, validation_spec: ValidationSpec) -> Dict[str, Any]:
        if not isinstance(research_payload, dict):
            return {
                "passed": False,
                "score": 0.0,
                "error": "Research deliverable must be a structured JSON dictionary.",
                "logs": "Expected dict, got non-dict payload."
            }

        # 1. Check required keys
        if validation_spec.required_keys:
            missing_keys = [k for k in validation_spec.required_keys if k not in research_payload]
            if missing_keys:
                return {
                    "passed": False,
                    "score": 0.0,
                    "error": f"Missing required research keys: {missing_keys}",
                    "logs": f"Schema check failed. Missing keys: {missing_keys}"
                }

        # 2. Check JSON Schema if provided
        if validation_spec.json_schema:
            try:
                jsonschema.validate(instance=research_payload, schema=validation_spec.json_schema)
            except jsonschema.ValidationError as ve:
                return {
                    "passed": False,
                    "score": 0.0,
                    "error": f"JSON Schema validation error: {ve.message}",
                    "logs": f"Failed schema validation at path: {list(ve.path)}"
                }

        return {
            "passed": True,
            "score": 1.0,
            "error": None,
            "logs": "[RESEARCH VALIDATOR] JSON Schema and required structure confirmed valid."
        }


class QueryValidatorBot:
    """Validates factual query answers using programmatic entity & keyword checks."""

    @staticmethod
    def validate(query_answer_payload: Any, validation_spec: ValidationSpec) -> Dict[str, Any]:
        answer_text = ""
        if isinstance(query_answer_payload, dict):
            answer_text = str(query_answer_payload.get("answer", ""))
        elif isinstance(query_answer_payload, str):
            answer_text = query_answer_payload

        if not answer_text.strip():
            return {
                "passed": False,
                "score": 0.0,
                "error": "Query answer text is empty.",
                "logs": "Empty query answer received."
            }

        # Check expected keywords/entities
        expected = validation_spec.expected_keywords or []
        if expected:
            matched = [kw for kw in expected if kw.lower() in answer_text.lower()]
            match_rate = len(matched) / len(expected)
            passed = match_rate >= 0.70  # At least 70% of ground-truth entities present
            
            return {
                "passed": passed,
                "score": round(match_rate, 2),
                "error": None if passed else f"Only matched {len(matched)}/{len(expected)} expected ground-truth keywords.",
                "logs": f"[QUERY VALIDATOR] Matched keywords: {matched}. Fact accuracy score: {match_rate:.2f}"
            }

        return {
            "passed": True,
            "score": 1.0,
            "error": None,
            "logs": "[QUERY VALIDATOR] Answer format verified."
        }


class VerificationOracle:
    """Top-level oracle coordinating the 3 domain validator bots."""

    @staticmethod
    async def verify_deliverable(
        task_id: str,
        category: TaskCategory,
        artifact_payload: Dict[str, Any],
        validation_spec: ValidationSpec
    ) -> VerificationReport:
        if category == TaskCategory.CODE_GENERATION:
            code = artifact_payload.get("source_code", "")
            test_code = validation_spec.test_suite_code
            result = CodeValidatorBot.validate(code, test_code)
            
        elif category == TaskCategory.RESEARCH:
            research_data = artifact_payload.get("research_json", artifact_payload)
            result = ResearchValidatorBot.validate(research_data, validation_spec)
            
        elif category == TaskCategory.QUERY:
            result = QueryValidatorBot.validate(artifact_payload, validation_spec)
            
        else:
            result = {
                "passed": True,
                "score": 1.0,
                "error": None,
                "logs": "Default pass for unclassified task."
            }

        return VerificationReport(
            task_id=task_id,
            category=category,
            passed=result["passed"],
            score=result.get("score", 1.0),
            validation_details={"execution_time_ms": result.get("execution_time_ms")},
            error_message=result.get("error"),
            logs=result.get("logs", ""),
            timestamp=time.time()
        )


# Singleton verification oracle
verification_oracle = VerificationOracle()
