# 후보 추출

과업: 한국어 법률 텍스트에서 은유 후보 표현을 넓게 추출한다.

- 최종 은유 판정은 하지 않는다.
- recall-oriented로 후보를 수집한다.
- 명백히 문자적인 법률 전문어는 과잉 포함하지 않는다.
- 원문 표현을 그대로 보존한다.
- 형태소/품사 힌트가 가능하면 `morphemes`에 기록한다.
- 출력은 JSON만 허용한다.

입력:
{{INPUT_TEXT}}

출력 JSON:
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
