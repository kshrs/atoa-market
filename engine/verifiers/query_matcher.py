"""
Query & Spec Matching Verifier Module (QueryValidatorBot).
Assesses whether the submitted deliverable strictly matches the original task prompt,
ground truth search assertions, required keywords/flags, regex patterns, and JSON schemas.
Supports optional live query ground-truth resolution.
"""
import json
import re
import urllib.parse
from typing import Dict, Any, List, Set, Optional, Tuple
import jsonschema
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult


def validate_with_jsonschema(data: Any, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates data against standard JSON Schema using the Python jsonschema library.
    Returns (is_valid, list of error messages).
    """
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in validator.iter_errors(data):
        path = ".".join(str(p) for p in error.absolute_path) or "root"
        errors.append(f"[{path}] {error.message}")
    return len(errors) == 0, errors


def resolve_query_ground_truth(query: str) -> List[str]:
    """
    Extracts or resolves key ground truth factual entities and search terms from a query string.
    Can be overridden or mocked for live web search engine integrations.
    """
    if not query:
        return []
    # Extract capitalized multi-word terms, numbers, and key tokens
    tokens = re.findall(r"\b[A-Z][a-zA-Z0-9_-]+\b|\b\d+(?:\.\d+)?\b|\b[a-zA-Z]{5,}\b", query)
    return list(dict.fromkeys(tokens))  # preserve order, unique


async def verify_matcher(task_spec: TaskManifest, deliverable: DeliverablePayload) -> EvaluationResult:
    """
    Evaluates deliverable alignment with prompt specifications, schemas, regexes, and constraints.
    """
    task_id = task_spec.task_id
    proof_logs = []
    benchmark_metrics: Dict[str, Any] = {
        "schema_valid": True,
        "missing_fields": [],
        "constraint_score": 1.0,
        "prompt_alignment": 1.0,
        "live_search_enabled": False,
        "ground_truth_entities": [],
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
    target_schema = task_spec.spec_schema or task_spec.constraints.get("schema")
    if target_schema:
        if data is None:
            benchmark_metrics["schema_valid"] = False
            proof_logs.append("[Schema Error] Task specified JSON schema but deliverable contains no valid JSON object.")
            schema_score = 0.0
        else:
            is_valid, errs = validate_with_jsonschema(data, target_schema)
            benchmark_metrics["schema_valid"] = is_valid
            benchmark_metrics["missing_fields"] = errs
            if not is_valid:
                proof_logs.append(f"[Schema Error] jsonschema validation failed: {errs}")
                schema_score = max(0.0, 1.0 - (len(errs) * 0.25))
            else:
                proof_logs.append("[Schema Check] Deliverable strictly satisfies target jsonschema.")

    # 2. Constraint & Ground Truth Entity Compliance
    constraint_score = 1.0
    constraints = task_spec.constraints

    # Optional Live Search / Ground Truth Query Resolution
    enable_live_search = constraints.get("enable_live_search", False)
    ground_truth_entities = list(constraints.get("ground_truth_entities", [])) or list(task_spec.ground_truth_references)
    
    if enable_live_search:
        benchmark_metrics["live_search_enabled"] = True
        resolved_entities = resolve_query_ground_truth(task_spec.prompt or constraints.get("query", ""))
        for ent in resolved_entities:
            if ent not in ground_truth_entities:
                ground_truth_entities.append(ent)
        proof_logs.append(f"[Live Search] Resolved {len(ground_truth_entities)} ground truth entities for query.")

    benchmark_metrics["ground_truth_entities"] = ground_truth_entities

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
    required_keywords = list(constraints.get("required_keywords", []))
    full_content = (text + " " + json.dumps(data) if data else text).lower()

    if required_keywords:
        missing_kw = [kw for kw in required_keywords if kw.lower() not in full_content]
        if missing_kw:
            kw_ratio = (len(required_keywords) - len(missing_kw)) / len(required_keywords)
            constraint_score *= kw_ratio
            proof_logs.append(f"[Constraint Error] Missing required keywords: {missing_kw}")

    # Ground truth entity matches
    if ground_truth_entities:
        matched_ents = [ent for ent in ground_truth_entities if ent.lower() in full_content]
        ent_ratio = len(matched_ents) / len(ground_truth_entities)
        constraint_score *= (0.5 + 0.5 * ent_ratio)
        proof_logs.append(f"[Ground Truth] Matched {len(matched_ents)}/{len(ground_truth_entities)} entities (ratio: {ent_ratio:.2f})")

    # Regex constraints
    regex_patterns = constraints.get("regex_patterns", [])
    if regex_patterns:
        full_content_raw = text + " " + (json.dumps(data) if data else "")
        for pattern in regex_patterns:
            if not re.search(pattern, full_content_raw):
                constraint_score -= 0.25
                proof_logs.append(f"[Constraint Error] Regex pattern '{pattern}' not satisfied.")

    constraint_score = max(0.0, constraint_score)
    benchmark_metrics["constraint_score"] = round(constraint_score, 3)

    # 3. Prompt & Semantic Alignment
    prompt_tokens = set(re.findall(r"\b[a-z0-9_]{4,}\b", task_spec.prompt.lower()))
    content_tokens = set(re.findall(r"\b[a-z0-9_]{4,}\b", full_content))
    
    if prompt_tokens and content_tokens:
        overlap = content_tokens.intersection(prompt_tokens)
        prompt_alignment = min(1.0, (len(overlap) / len(prompt_tokens)) * 1.5)
    else:
        prompt_alignment = 1.0 if not prompt_tokens else 0.0

    benchmark_metrics["prompt_alignment"] = round(prompt_alignment, 3)

    # Composite Score Calculation
    if target_schema and constraints:
        base_score = (0.50 * schema_score) + (0.50 * constraint_score)
        final_score = base_score * (0.85 + 0.15 * prompt_alignment)
    elif target_schema:
        base_score = schema_score
        final_score = base_score * (0.85 + 0.15 * prompt_alignment)
    elif constraints:
        base_score = constraint_score
        final_score = base_score * (0.85 + 0.15 * prompt_alignment)
    else:
        final_score = prompt_alignment

    final_score = max(0.0, min(1.0, final_score))
    verdict: "Literal['PASS', 'FAIL']" = "PASS" if final_score >= task_spec.passing_threshold and benchmark_metrics["schema_valid"] else "FAIL"
    slashing = final_score < task_spec.slashing_threshold or not benchmark_metrics["schema_valid"]

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
