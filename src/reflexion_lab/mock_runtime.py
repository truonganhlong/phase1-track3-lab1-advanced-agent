from __future__ import annotations
import json
import time
import urllib.request
from urllib.error import HTTPError, URLError

from .prompts import ACTOR_SYSTEM, EVALUATOR_SYSTEM, REFLECTOR_SYSTEM
from .schemas import QAExample, JudgeResult, ReflectionEntry
from .utils import normalize_answer

FAILURE_MODE_BY_QID = {"hp2": "incomplete_multi_hop", "hp4": "wrong_final_answer", "hp6": "entity_drift", "hp8": "entity_drift"}


def _call_ollama(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    ollama_host: str,
    as_json: bool = False,
) -> tuple[str, int, int]:
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        "stream": False,
    }
    if as_json:
        payload["format"] = "json"

    req = urllib.request.Request(
        url=f"{ollama_host.rstrip('/')}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Ollama HTTP error: {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot connect to Ollama at {ollama_host}: {exc.reason}") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    content = body.get("message", {}).get("content", "").strip()
    token_estimate = int(body.get("prompt_eval_count", 0)) + int(body.get("eval_count", 0))
    return content, token_estimate, latency_ms


def _build_context_text(example: QAExample) -> str:
    return "\n".join(f"- {chunk.title}: {chunk.text}" for chunk in example.context)


def actor_answer(
    example: QAExample,
    attempt_id: int,
    agent_type: str,
    reflection_memory: list[str],
    model: str,
    ollama_host: str,
) -> tuple[str, int, int]:
    reflections = "\n".join(f"- {note}" for note in reflection_memory) if reflection_memory else "- (none)"
    user_prompt = f"""
Question: {example.question}

Context:
{_build_context_text(example)}

Agent type: {agent_type}
Attempt: {attempt_id}
Reflection memory:
{reflections}
"""
    answer, tokens, latency = _call_ollama(
        model=model,
        system_prompt=ACTOR_SYSTEM,
        user_prompt=user_prompt,
        ollama_host=ollama_host,
    )
    return answer.strip(), tokens, latency


def evaluator(
    example: QAExample,
    answer: str,
    model: str,
    ollama_host: str,
) -> tuple[JudgeResult, int, int]:
    # Keep an exact-match fallback to avoid evaluator drift for clear matches.
    if normalize_answer(example.gold_answer) == normalize_answer(answer):
        return (
            JudgeResult(
                score=1.0,
                is_correct=True,
                reason="Final answer matches gold answer after normalization.",
                failure_mode="none",
                extracted_answer=normalize_answer(answer),
                confidence=1.0,
            ),
            0,
            0,
        )

    user_prompt = f"""
Question: {example.question}
Gold answer: {example.gold_answer}
Predicted answer: {answer}

Return only valid JSON with the required fields.
"""
    raw, tokens, latency = _call_ollama(
        model=model,
        system_prompt=EVALUATOR_SYSTEM,
        user_prompt=user_prompt,
        ollama_host=ollama_host,
        as_json=True,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "score": 0,
            "is_correct": False,
            "reason": "Evaluator produced invalid JSON; fallback marked incorrect.",
            "failure_mode": "wrong_final_answer",
            "extracted_answer": normalize_answer(answer),
            "confidence": 0.0,
        }
    parsed.setdefault("failure_mode", "wrong_final_answer")
    parsed.setdefault("extracted_answer", normalize_answer(answer))
    result = JudgeResult.model_validate(parsed)
    return result, tokens, latency


def reflector(
    example: QAExample,
    attempt_id: int,
    answer: str,
    judge: JudgeResult,
    model: str,
    ollama_host: str,
) -> tuple[ReflectionEntry, int, int]:
    user_prompt = f"""
Question: {example.question}
Context:
{_build_context_text(example)}
Previous answer: {answer}
Evaluator reason: {judge.reason}
Failure mode: {judge.failure_mode or "unknown"}

Return only valid JSON with the required fields.
"""
    raw, tokens, latency = _call_ollama(
        model=model,
        system_prompt=REFLECTOR_SYSTEM,
        user_prompt=user_prompt,
        ollama_host=ollama_host,
        as_json=True,
    )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "error_analysis": "Answer did not satisfy evaluator.",
            "lesson": "Need stricter multi-hop grounding in provided context.",
            "strategy": "Extract hop-1 entity, then hop-2 entity before finalizing.",
        }
    parsed["attempt_id"] = attempt_id
    reflection = ReflectionEntry.model_validate(parsed)
    return reflection, tokens, latency
