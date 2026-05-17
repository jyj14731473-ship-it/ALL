# 검증

과업: MIPVU 판단, 개념 은유 분류, RDF-ready 매핑의 논리적 일관성을 검토한다.

점검:
- invalid JSON 또는 누락 필드
- `distinctness=false`인데 MRW 계열인지
- `similarity=false`인데 MRW 계열인지
- source_domain 또는 target_domain 누락
- 허용되지 않은 RDF predicate
- confidence가 낮아 인간 검토가 필요한 경우
- 법률 관습 은유의 과잉 탐지 가능성

출력 JSON:
```json
{
  "is_valid": true,
  "repair_needed": false,
  "human_review_needed": false,
  "issues": [
    {
      "severity": "warning",
      "location": "",
      "message": "",
      "suggested_fix": ""
    }
  ]
}
```
