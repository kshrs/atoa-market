"""
Researcher Verifier Module.
Validates factual deliverables, claim-source grounding, citation integrity, and structural completeness.
"""
import re
import urllib.parse
from typing import Dict, Any, List, Set
from engine.models import TaskManifest, DeliverablePayload, EvaluationResult


def _extract_tokens(text: str) -> Set[str]:
    """Tokenizes text into lowercase alpha words."""
    return set(re.findall(r"\b[a-z0-9_]{3,}\b", text.lower()))


def _is_valid_source(source_str: str, allowed_sources: List[str]) -> bool:
    """Checks if a source is structurally valid and belongs to allowed ground truth if specified."""
    if not source_str:
        return False
    parsed = urllib.parse.urlparse(source_str)
    # Check if valid URL or valid document reference
    is_valid_url = bool(parsed.scheme in ("http", "https") and parsed.netloc)
    is_valid_doc = bool(re.match(r"^[a-zA-Z0-9_\-\.\/\\]+$", source_str.strip()))
    
    if not (is_valid_url or is_valid_doc):
        return False

    if allowed_sources:
        # Check if source matches or is a prefix/domain match of allowed sources
        for allowed in allowed_sources:
            if allowed.lower() in source_str.lower() or source_str.lower() in allowed.lower():
                return True
        return False
    return True


async def verify_researcher(task_spec: TaskManifest, deliverable: DeliverablePayload) -> EvaluationResult:
    """
    Evaluates research deliverables (summaries, papers, datasets) for grounding, citation validity, and structure.
    """
    task_id = task_spec.task_id
    text = deliverable.submitted_text or ""
    if not text and deliverable.submitted_data:
        text = str(deliverable.submitted_data)

    proof_logs = []
    benchmark_metrics: Dict[str, Any] = {
        "word_count": len(text.split()),
        "citations_total": len(deliverable.citations),
        "citations_valid": 0,
        "grounding_score": 0.0,
        "completeness_score": 0.0,
        "hallucination_penalty": 0.0,
    }

    if not text.strip():
        return EvaluationResult(
            task_id=task_id,
            verdict="FAIL",
            score=0.0,
            slashing_recommended=True,
            benchmark_metrics=benchmark_metrics,
            proof_logs="FAIL: Empty research deliverable submitted.",
            details={"error": "Empty text deliverable"}
        )

    # 1. Structural Completeness
    min_words = int(task_spec.constraints.get("min_words", 50))
    max_words = int(task_spec.constraints.get("max_words", 100000))
    word_count = len(text.split())
    benchmark_metrics["word_count"] = word_count

    completeness = 1.0
    if word_count < min_words:
        completeness *= (word_count / max_words if max_words else word_count / min_words)
        proof_logs.append(f"[Completeness Warning] Word count {word_count} is below min required {min_words}")
    elif word_count > max_words:
        completeness *= max(0.7, max_words / word_count)
        proof_logs.append(f"[Completeness Warning] Word count {word_count} exceeds max {max_words}")

    # Check required sections / keywords
    required_sections = task_spec.constraints.get("required_sections", [])
    if required_sections:
        missing_secs = [sec for sec in required_sections if sec.lower() not in text.lower()]
        if missing_secs:
            sec_ratio = (len(required_sections) - len(missing_secs)) / len(required_sections)
            completeness *= sec_ratio
            proof_logs.append(f"[Completeness Warning] Missing required sections: {missing_secs}")

    benchmark_metrics["completeness_score"] = round(completeness, 3)

    # 2. Citation Integrity & Grounding
    allowed_sources = task_spec.ground_truth_references or task_spec.constraints.get("allowed_sources", [])
    citations = deliverable.citations
    valid_citations = 0
    grounding_score = 1.0

    if citations:
        for cit in citations:
            claim = cit.get("claim", "")
            source = cit.get("source", "")
            if _is_valid_source(source, allowed_sources):
                valid_citations += 1
            else:
                proof_logs.append(f"[Citation Invalid] Source '{source}' not valid or not in allowed ground truth")
        
        benchmark_metrics["citations_valid"] = valid_citations
        citation_ratio = valid_citations / len(citations) if citations else 0.0
    else:
        # Check if citations were required
        if task_spec.constraints.get("require_citations", False):
            citation_ratio = 0.0
            proof_logs.append("[Citation Warning] Citations were required but none were provided.")
        else:
            citation_ratio = 1.0

    # 3. Ground truth token alignment / Hallucination check
    if allowed_sources and task_spec.ground_truth_references:
        gt_tokens: Set[str] = set()
        for ref in task_spec.ground_truth_references:
            gt_tokens.update(_extract_tokens(ref))

        deliv_tokens = _extract_tokens(text)
        if gt_tokens and deliv_tokens:
            common = deliv_tokens.intersection(gt_tokens)
            grounding_score = len(common) / len(deliv_tokens) if deliv_tokens else 0.0
            # Scale grounding score with a reasonable factor
            grounding_score = min(1.0, grounding_score * 3.0)  # text contains stopwords and extra explanations
        else:
            grounding_score = 0.5
    else:
        grounding_score = 1.0

    benchmark_metrics["grounding_score"] = round(grounding_score, 3)

    # Calculate Hallucination penalty
    hallucination_penalty = 0.0
    if grounding_score < 0.2:
        hallucination_penalty = 0.5
        proof_logs.append(f"[Hallucination Alert] Low grounding score: {grounding_score:.2f}")

    benchmark_metrics["hallucination_penalty"] = hallucination_penalty

    # Composite Score Calculation
    # 40% completeness, 35% citation ratio, 25% grounding minus penalties
    raw_score = (0.40 * completeness) + (0.35 * citation_ratio) + (0.25 * grounding_score) - hallucination_penalty
    final_score = max(0.0, min(1.0, raw_score))

    verdict: "Literal['PASS', 'FAIL']" = "PASS" if final_score >= task_spec.passing_threshold else "FAIL"
    slashing = final_score < task_spec.slashing_threshold

    proof_logs.append(f"[Score Summary] Completeness={completeness:.2f}, Citations={citation_ratio:.2f}, Grounding={grounding_score:.2f} -> Final Score={final_score:.2f}")

    return EvaluationResult(
        task_id=task_id,
        verdict=verdict,
        score=round(final_score, 4),
        slashing_recommended=slashing,
        benchmark_metrics=benchmark_metrics,
        proof_logs="\n".join(proof_logs),
        details={"word_count": word_count, "citations": deliverable.citations}
    )
