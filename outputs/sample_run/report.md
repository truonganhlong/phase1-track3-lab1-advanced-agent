# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_mini.json
- Mode: ollama
- Records: 16
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.75 | 0.875 | 0.125 |
| Avg attempts | 1 | 1.25 | 0.25 |
| Avg token estimate | 281.75 | 454.88 | 173.13 |
| Avg latency (ms) | 29936.75 | 54856.5 | 24919.75 |

## Failure modes
```json
{
  "react": {
    "none": 6,
    "wrong_final_answer": 1,
    "entity_drift": 1
  },
  "reflexion": {
    "none": 7,
    "entity_drift": 1
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding

## Discussion
Reflexion helps when the first attempt stops after the first hop or drifts to a wrong second-hop entity. The tradeoff is higher attempts, token cost, and latency. In a real report, students should explain when the reflection memory was useful, which failure modes remained, and whether evaluator quality limited gains.
