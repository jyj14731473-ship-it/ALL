# MIPVU 판단 (3a, 3b, 3c)

과업: 후보별로 MIPVU-informed 절차를 수행한다.

순서:
1. Contextual meaning (문맥 의미) 기록
2. Basic meaning(기본 의미) 기록
3. Meaning contrast + distinctness + comparison_possible + similarity 판단
4. MIPVU 라벨 지정

라벨은 반드시 다음 중 하나만 사용한다:
- `MRW`
- `MRW_candidate`
- `borderline_candidate`
- `non_MRW`
- `uncertain`

주의:
- 출력에는 판단 결과 필드만 쓴다. 입력에 있는 sentence, lemma, pos, meaning 필드를 반복해서 쓰지 마라.
- `basic_meaning`이 비어 있거나 `basic_meaning_source`가 `unavailable`이면, 일반 어휘 지식으로 조심스럽게 판단할 수 있으나 confidence를 낮추고 `needs_human_review=true`로 둔다.
- 문맥상 의미와 기본 의미 대비를 확정할 수 없으면 `uncertain`을 사용한다.

입력:
{{CANDIDATES_JSON}}

출력 스키마(JSON):
```json
{
  "judgments": [
    {
      "candidate_id": "C001",
      "mipvu_label": "MRW_candidate",
      "judgment_reason": "",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ]
}
```
