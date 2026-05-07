# MIPVU 판단

과업: 후보별로 MIPVU-informed 절차를 수행한다.

순서:
1. 문맥 의미를 법률 기능까지 포함해 기록한다.
2. 기본 의미를 기록한다. 표준국어대사전 조회 결과가 있으면 우선한다.
3. `distinctness`를 판단한다.
4. `comparison_possible`과 `similarity`를 판단한다.
5. `mipvu_label`을 지정한다.

라벨:
- MRW
- MRW_candidate
- borderline_candidate
- non_MRW
- uncertain

후보 입력:
{{CANDIDATES_JSON}}

출력 JSON:
```json
{
  "judgments": [
    {
      "candidate_id": "C001",
      "sentence_id": "S001",
      "token": "",
      "lemma": "",
      "pos": "",
      "context_sentence": "",
      "contextual_meaning": "",
      "basic_meaning": "",
      "basic_meaning_source": "stdict",
      "meaning_contrast": "",
      "distinctness": true,
      "comparison_possible": true,
      "similarity": true,
      "mipvu_label": "MRW_candidate",
      "judgment_reason": "",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ]
}
```
