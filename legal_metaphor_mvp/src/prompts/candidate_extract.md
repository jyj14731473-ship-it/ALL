# 후보 추출

과업: 한국어 법률 텍스트에서 은유 후보 표현을 넓게 추출하되, 정형적 법률 관용표현은 과잉 추출하지 않는다.

- 최종 은유 판정은 하지 않는다.
- recall-oriented로 후보를 수집하되, 법률 고정어/조문상 표현은 보수적으로 포함한다.
- 원문 표현은 그대로 보존한다.
- 출력은 JSON만 허용한다. 코드블록, 설명문, 추가 키/텍스트 금지.

입력:
{{INPUT_TEXT}}

출력 스키마(JSON):
```json
{
  "candidates": [
    {
      "candidate_id": "C001",
      "sentence_id": "S001",
      "sentence": "",
      "surface_expression": "",
      "lemma": "",
      "pos": "",
      "morphemes": [{"token": "", "pos": ""}],
      "context_window": "",
      "opinion_type": "unknown",
      "extraction_reason": "",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ]
}
```
