"""
Query & Spec Matching Verifier Module.
Assesses whether the submitted deliverable strictly matches the original task prompt,
constraints, required keywords, and JSON input/output schemas.
"""
import json
import re
from typing import Dict, Any, List, Set, Optional, Tuple
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult


def _validate_schema(data: Any, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates data against a json-schema-like dictionary.
    Supports 'type', 'required', and 'properties'.
    """
    errors = []
    if not isinstance(schema, dict):
        return True, []

    expected_type = schema.get("type")
    if expected_type:
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }
        py_type = type_map.get(expected_type)
        if py_type and not isinstance(data, py_type):
            errors.append(f"Expected root type '{expected_type}', got '{type(data).__name__}'")
            return False, errors

    if isinstance(data, dict):
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field '{field}'")

        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name in data and isinstance(prop_schema, dict):
                prop_type_str = prop_schema.get("type")
                if prop_type_str:
                    prop_py_type = {
                        "object": dict,
                        "array": list,
                        "string": str,
                        "number": (int, float),
                        "integer": int,
                        "boolean": bool,
                    }.get(prop_type_str)
                    if prop_py_type and not isinstance(data[prop_name], prop_py_type):
                        errors.append(f"Field '{prop_name}' expected type '{prop_type_str}', got '{type(data[prop_name]).__name__}'")

    return len(errors) == 0, errors


async def verify_matcher(task_spec: TaskManifest, deliverable: DeliverablePayload) -> EvaluationResult:
    """
    Evaluates deliverable alignment with prompt specifications, schemas, and constraints.
    """
    task_id = task_spec.task_id
    proof_logs = []
    benchmark_metrics: Dict[str, Any] = {
        "schema_valid": True,
        "missing_fields": [],
        "constraint_score": 1.0,
        "prompt_alignment": 1.0,
    }

    # Extract deliverable content for matching
    data = deliverable.submitted_data
    text = deliverable.submitted_text or ""
    if data is None and text:
        try:
            data = json.loads(text)
        except Exception:
            pass

    # 1. Spec Schema Validation (if schema specified)
    schema_score = 1.0
    if task_spec.spec_schema:
        if data is None:
            benchmark_metrics["schema_valid"] = False
            proof_logs.append("[Schema Error] Task specified JSON schema but deliverable contains no valid JSON object.")
            schema_score = 0.0
        else:
            is_valid, errs = _validate_schema(data, task_spec.spec_schema)
            benchmark_metrics["schema_valid"] = is_valid
            benchmark_metrics["missing_fields"] = errs
            if not is_valid:
                proof_logs.append(f"[Schema Error] Schema validation failed with errors: {errs}")
                schema_score = max(0.0, 1.0 - (len(errs) * 0.3))
            else:
                proof_logs.append("[Schema Check] Deliverable strictly satisfies target schema.")

    # 2. Constraint Compliance
    constraint_score = 1.0
    constraints = task_spec.constraints

    # Required format (e.g. "json", "markdown", "csv")
    required_format = constraints.get("format")
    if required_format:
        if required_format.lower() == "json" and data is None:
            constraint_score -= 0.5
            proof_logs.append("[Constraint Error] Output was not valid JSON as requested.")
        elif required_format.lower() == "markdown" and not ("#" in text or "```" in text or "*" in text):
            constraint_score -= 0.2
            proof_logs.append("[Constraint Warning] Deliverable does not appear to use Markdown formatting.")

    # Required Keywords / Flags
    required_keywords = constraints.get("required_keywords", [])
    if required_keywords:
        full_content = (text + " " + json.dumps(data) if data else text).lower()
        missing_kw = [kw for kw in required_keywords if kw.lower() not in full_content]
        if missing_kw:
            kw_ratio = (len(required_keywords) - len(missing_kw)) / len(required_keywords)
            constraint_score *= kw_ratio
            proof_logs.append(f"[Constraint Error] Missing required keywords: {missing_kw}")

    # Regex constraints
    regex_patterns = constraints.get("regex_patterns", [])
    if regex_patterns:
        full_content = text + " " + (json.dumps(data) if data else "")
        for pattern in regex_patterns:
            if not re.search(pattern, full_content):
                constraint_score -= 0.25
                proof_logs.append(f"[Constraint Error] Regex pattern '{pattern}' not satisfied.")

    constraint_score = max(0.0, constraint_score)
    benchmark_metrics["constraint_score"] = round(constraint_score, 3)

    # 3. Prompt & Semantic Alignment
    prompt_tokens = set(re.findall(r"\b[a-z0-9_]{4,}\b", task_spec.prompt.lower()))
    content_tokens = set(re.findall(r"\b[a-z0-9_]{4,}\b", (text + " " + json.dumps(data) if data else text).lower()))
    
    if prompt_tokens and content_tokens:
        overlap = content_tokens.intersection(prompt_tokens)
        prompt_alignment = min(1.0, (len(overlap) / len(prompt_tokens)) * 1.5)
    else:
        prompt_alignment = 1.0 if not prompt_tokens else 0.0

    benchmark_metrics["prompt_alignment"] = round(prompt_alignment, 3)

    # Composite Score Calculation
    has_constraints = bool(task_spec.constraints or task_spec.spec_schema)
    if task_spec.spec_schema and task_spec.constraints:
        base_score = (0.50 * schema_score) + (0.50 * constraint_score)
        final_score = base_score * (0.85 + 0.15 * prompt_alignment)
    elif task_spec.spec_schema:
        base_score = schema_score
        final_score = base_score * (0.85 + 0.15 * prompt_alignment)
    elif task_spec.constraints:
        base_score = constraint_score
        final_score = base_score * (0.85 + 0.15 * prompt_alignment)
    else:
        final_score = prompt_alignment

    final_score = max(0.0, min(1.0, final_score))
    verdict: "Literal['PASS', 'FAIL']" = "PASS" if final_score >= task_spec.passing_threshold else "FAIL"
    slashing = final_score < task_spec.slashing_threshold

    proof_logs.append(f"[Score Summary] Schema={schema_score:.2f}, Constraints={constraint_score:.2f}, PromptAlign={prompt_alignment:.2f} -> Final Score={final_score:.2f}")

    return EvaluationResult(
        task_id=task_id,
        verdict=verdict,
        score=round(final_score, 4),
        slashing_recommended=slashing,
        benchmark_metrics=benchmark_metrics,
        proof_logs="\n".join(proof_logs),
        details={"missing_fields": benchmark_metrics["missing_fields"]}
    )
