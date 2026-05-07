## Prompt Architecture (Legal Metaphor MVP)

본 문서는 LangGraph 공식 파이프라인(`--pipeline graph`)에서 프롬프트를 어디까지 쓰는지 기준을 고정합니다.

### 1) 현재 운영되는 프롬프트 단계

- `candidate_extract.md`
  - 입력: `raw_text`
  - 출력: `candidates`
  - 목적: 은유 후보 후보군 추출

- `mipvu_judge.md`
  - 입력: `candidates` (+ dictionary lookup 보강 결과)
  - 출력: `judgments`
  - 목적: MIPVU-informed 라벨(`MRW`, `MRW_candidate`, `borderline_candidate`, `non_MRW`) 산출

- `metaphor_classify.md`
  - 입력: `raw_text`, `candidates`, `judgments`
  - 출력: `metaphors`
  - 목적: 개념적 은유 주석(메타포 유닛) 정리

### 2) 프롬프트 미사용(규칙 기반) 단계

- `rdf_mapping` 노드: `metaphor_annotations`를 `fallback_mapping_from_annotation`으로 결정론적으로 RDF 매핑 생성
- `validation_check` 노드: 규칙 기반 predicate/필드 유효성 검사
- `rdf_convert` 노드: Turtle 문자열 변환(`mappings_to_turtle`)

### 3) 문서/주요 파일

- 노드 정의: `src/graph/annotation_graph.py`
- LLM 유틸: `src/graph/prompt_utils.py`
- RDF 변환 엔진: `src/rdf/convert.py`
- 스테이트/스키마: `src/schemas/annotation.py`

### 4) 프롬프트 변경 시 체크리스트

1. 변경 대상 노드가 LLM 노드인지 먼저 판단한다.
2. 입력/출력 키가 `schemas.annotation`의 계약(`candidate_id`, `judgment`, `metaphor`)과 일치하는지 확인한다.
3. JSON 형식만 출력되도록 프롬프트를 유지한다.
4. `--pipeline graph`로 엔드투엔드 실행해 `errors`, `status`, `rdf_output` 유무를 확인한다.
5. `test_graph_pipeline.py`의 안정성 기대값(특히 `metadata.llm_available`, `ttl 파일 생성`)이 깨지지 않도록 확인한다.

참고: `src/prompts/rdf_mapping.md`, `src/prompts/validation_check.md`는 현재 그래프 공식 경로에서 직접 호출되지 않습니다.
