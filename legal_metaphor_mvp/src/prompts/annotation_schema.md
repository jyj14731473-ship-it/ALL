# Canonical Annotation Schema

최종 은유 주석은 다음 구조를 따른다.

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

`metaphor_type`: structural, ontological, orientational, uncertain.
`opinion_type`: majority, dissenting, concurring, unknown.
