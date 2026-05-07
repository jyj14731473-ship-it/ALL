# 은유 분류

과업: `MRW`, `MRW_candidate`, `borderline_candidate` 항목만 개념 은유로 분류한다.

- source_domain, target_domain, conceptual_metaphor를 안정적 라벨로 기록한다.
- 너무 세부적인 원천영역을 억지로 만들지 않는다.
- 불확실하면 `metaphor_type`은 `uncertain`, confidence는 낮게 둔다.
- 출력은 JSON만 허용한다.

입력:
{{JUDGMENTS_JSON}}

출력 JSON:
```json
{
  "metaphors": [
    {
      "metaphor_id": "M001",
      "candidate_id": "C001",
      "sentence_id": "S001",
      "surface_expression": "",
      "context_sentence": "",
      "conceptual_metaphor": "",
      "metaphor_type": "structural",
      "source_domain": "",
      "target_domain": "",
      "legal_concept": "",
      "opinion_type": "unknown",
      "is_legal_domain_specific": false,
      "classification_reason": "",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ]
}
```
