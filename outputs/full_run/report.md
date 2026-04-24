# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_full.json
- Mode: ollama
- Records: 240
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.9417 | 1.0 | 0.0583 |
| Avg attempts | 1 | 1.1 | 0.1 |
| Avg token estimate | 266.37 | 334.39 | 68.02 |
| Avg latency (ms) | 34081.51 | 53996.97 | 19915.46 |

## Failure modes
```json
{
  "react": {
    "none": 113,
    "wrong_final_answer": 7
  },
  "reflexion": {
    "none": 120
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
