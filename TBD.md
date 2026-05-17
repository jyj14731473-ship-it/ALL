# TBD - 미해결 결정 사항

이 문서는 향후 결정해야 할 사항을 추적합니다.

## Phase 2 진입 전 결정 필요

- (없음)

## Phase 2 중 결정

- UTF-8 decode fallback policy (M2-1 검토)
  - 출처: `AGENTS.md` Error Policy, `src/all_metaphor/io.py`
- Source/target domain labels when evidence insufficient (M2-5)
  - 출처: `skills/korean-mipvu/SKILL.md`, `src/all_metaphor/schemas.py`

## Phase 3 결정

- RDF inclusion confidence threshold (default 0.5 검증)
  - 출처: `AGENTS.md` Intermediate JSON Schema, `skills/korean-mipvu/references/edge_cases.md`

## 장기 (TBD)

- Direct metaphor handling
  - 출처: `AGENTS.md` Glossary, `skills/korean-mipvu/SKILL.md`, `skills/korean-mipvu/references/mipvu_protocol.md`
- Implicit metaphor handling
  - 출처: `AGENTS.md` Glossary, `skills/korean-mipvu/SKILL.md`, `skills/korean-mipvu/references/mipvu_protocol.md`
- Ontology alignment (RDF/RDFS/OWL/SKOS/legal ontologies)
  - 출처: `AGENTS.md` RDF Mapping Recommendation
- Future folder additions
  - 출처: `AGENTS.md` Folder Structure
- Config 확장: LLMSettings, ContextSettings, RetrySettings
  - 출처: `src/all_metaphor/config.py`
