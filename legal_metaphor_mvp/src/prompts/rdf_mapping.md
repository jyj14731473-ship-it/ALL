# RDF-ready 매핑

과업: 개념 은유 주석을 RDF-ready subject-predicate-object JSON으로 바꾼다.

- Turtle을 직접 출력하지 않는다.
- 의미적 subject, predicate, object 판단만 수행한다.
- predicate는 허용 목록에서만 선택한다.
- 출력은 JSON만 허용한다.

허용 predicate:
- ex:isConceptualizedAs
- ex:hasSourceDomain
- ex:hasTargetDomain
- ex:evokesFrame
- ex:hasMetaphorType
- ex:hasSurfaceExpression
- ex:appearsInSentence
- ex:hasMIPVULabel

입력:
{{METAPHORS_JSON}}

출력 JSON:
```json
{
  "rdf_mappings": [
    {
      "primary_triple": {
        "subject_label": "법체계",
        "subject_type": "LegalConcept",
        "subject_id": "LegalSystem",
        "predicate": "ex:isConceptualizedAs",
        "object_label": "질서",
        "object_type": "SourceDomain",
        "object_id": "Order"
      },
      "supporting_triples": [
        {
          "subject_label": "법질서의 통일성",
          "subject_type": "MetaphorAnnotation",
          "subject_id": "MetaphorAnnotation_001",
          "predicate": "ex:hasSurfaceExpression",
          "object_label": "법질서의 통일성",
          "object_type": "Literal",
          "object_id": "Literal_법질서의_통일성"
        }
      ],
      "mapping_reason": "",
      "confidence": 0.0,
      "needs_human_review": false
    }
  ]
}
```
