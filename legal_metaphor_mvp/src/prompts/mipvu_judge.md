# MIPVU 판단 (3a, 3b, 3c)

과업: 후보별로 MIPVU-informed 절차를 수행한다.

순서:
1. Contextual meaning (문맥 의미) 기록
2. Basic meaning(기본 의미) 기록
3. Meaning contrast + distinctness + comparison_possible + similarity 판단
4. MIPVU 라벨 지정

입력:
{{CANDIDATES_JSON}}

출력 스키마(JSON):
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
      "basic_meaning_source": "unavailable",
      "meaning_contrast": "",
      "distinctness": false,
      "comparison_possible": false,
      "similarity": false,
      "mipvu_label": "MRW_candidate",
      "judgment_reason": "",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ]
}
```
