from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from .mock_runtime import FAILURE_MODE_BY_QID, actor_answer, evaluator, reflector
from .schemas import AttemptTrace, QAExample, ReflectionEntry, RunRecord

@dataclass
class BaseAgent:
    agent_type: Literal["react", "reflexion"]
    max_attempts: int = 1
    model: str = "llama3.1:8b"
    ollama_host: str = "http://localhost:11434"

    def run(self, example: QAExample) -> RunRecord:
        reflection_memory: list[str] = []
        reflections: list[ReflectionEntry] = []
        traces: list[AttemptTrace] = []
        final_answer = ""
        final_score = 0.0
        last_failure_mode = "wrong_final_answer"
        for attempt_id in range(1, self.max_attempts + 1):
            answer, actor_tokens, actor_latency = actor_answer(
                example,
                attempt_id,
                self.agent_type,
                reflection_memory,
                self.model,
                self.ollama_host,
            )
            judge, eval_tokens, eval_latency = evaluator(
                example,
                answer,
                self.model,
                self.ollama_host,
            )

            token_estimate = actor_tokens + eval_tokens
            latency_ms = actor_latency + eval_latency
            trace = AttemptTrace(
                attempt_id=attempt_id,
                answer=answer,
                score=judge.score,
                reason=judge.reason,
                token_estimate=token_estimate,
                latency_ms=latency_ms,
            )
            final_answer = answer
            final_score = judge.score
            last_failure_mode = judge.failure_mode or "wrong_final_answer"
            if judge.is_correct:
                traces.append(trace)
                break

            if self.agent_type == "reflexion" and attempt_id < self.max_attempts:
                reflection, refl_tokens, refl_latency = reflector(
                    example,
                    attempt_id,
                    answer,
                    judge,
                    self.model,
                    self.ollama_host,
                )
                reflections.append(reflection)
                reflection_memory.append(
                    f"Lesson: {reflection.lesson} | Strategy: {reflection.strategy}"
                )
                trace.reflection = reflection
                trace.token_estimate += refl_tokens
                trace.latency_ms += refl_latency

            traces.append(trace)
        total_tokens = sum(t.token_estimate for t in traces)
        total_latency = sum(t.latency_ms for t in traces)
        failure_mode = (
            "none"
            if final_score >= 1
            else FAILURE_MODE_BY_QID.get(example.qid, last_failure_mode)
        )
        return RunRecord(qid=example.qid, question=example.question, gold_answer=example.gold_answer, agent_type=self.agent_type, predicted_answer=final_answer, is_correct=bool(final_score), attempts=len(traces), token_estimate=total_tokens, latency_ms=total_latency, failure_mode=failure_mode, reflections=reflections, traces=traces)

class ReActAgent(BaseAgent):
    def __init__(self, model: str = "llama3.1:8b", ollama_host: str = "http://localhost:11434") -> None:
        super().__init__(agent_type="react", max_attempts=1, model=model, ollama_host=ollama_host)

class ReflexionAgent(BaseAgent):
    def __init__(self, max_attempts: int = 3, model: str = "llama3.1:8b", ollama_host: str = "http://localhost:11434") -> None:
        super().__init__(agent_type="reflexion", max_attempts=max_attempts, model=model, ollama_host=ollama_host)
