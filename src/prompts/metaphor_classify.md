# 은유 분류

과업: `MRW`, `MRW_candidate`, `borderline_candidate` 항목만 최종 은유 주석으로 분류한다.

규칙:
- 과잉 분류를 피하고, source/target 매핑이 약하면 `uncertain` 처리.
- `source_domain`/`target_domain`이 불명확하면 보수적으로 낮은 confidence.
- 출력은 JSON만 허용한다.
- 출력에는 분류 결과 필드만 쓴다. 입력의 sentence, surface, context를 반복해서 쓰지 마라.

입력:
{{JUDGMENTS_JSON}}

출력 스키마(JSON):
```json
{
  "metaphors": [
    {
      "candidate_id": "C001",
      "conceptual_metaphor": "",
      "metaphor_type": "uncertain",
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
