# Legal Metaphor MVP

Korean legal text를 lemma 단위로 전처리하고, 사전 뜻과 문맥 뜻을 비교해 MIPVU 은유 판정 및 RDF/KG 산출물을 만드는 파이프라인입니다.

현재 유지하는 공식 경로는 하나입니다.

```bash
python src/main.py
```

`--pipeline full`은 호환용 옵션으로 남아 있지만 다른 pipeline 모드는 제거했습니다.

## Current Pipeline

1. `data/input.txt`를 문장/형태소/lemma group으로 변환
2. lemma group sanity cleanup
3. contextual meaning 생성
4. 표준국어대사전 lemma lookup
5. lemma 단위 MIPVU original meaning 판정
6. MIPVU 결과에서 source domain, target domain, conceptual metaphor, Lakoff-Johnson type 추출
7. RDF mapping, validation, Turtle, RDFLib KG 생성

## Outputs

기본 실행 시 생성/갱신되는 파일:

- `data/output/pos_nodes.json`
- `data/output/pos_nodes_corrected.json`
- `data/output/pos_nodes_corrected_report.json`
- `data/output/pos_nodes_contextualized.json`
- `data/output/pos_nodes_contextualized_report.json`
- `data/output/lemma_dictionary_lookup.json`
- `data/output/graph_annotation.json`
- `data/output/metaphors.ttl`
- `data/output/metaphor_kg.ttl`

`lemma_mipvu_judge` 결과는 별도 JSON이 아니라 `data/output/graph_annotation.json`의 `mipvu_annotations`에 들어갑니다.

## Environment

필수/선택 환경변수:

- `OPENAI_API_KEY`: contextual meaning과 lemma MIPVU LLM 판정에 사용
- `OPENAI_MODEL`: 기본값 `gpt-4.1-mini`
- `OPENAI_TEMPERATURE`: 기본값 `0`
- `STDICT_API_KEY`: 표준국어대사전 API 조회에 사용
- `STDICT_PAGE_SIZE`: 사전 조회 page size, 기본값 `100`

API 키가 없으면 파이프라인은 크래시하지 않고 기존 산출물 재사용 또는 fallback payload로 진행합니다.

## Run

전체 기본 실행:

```bash
python src/main.py
```

명시 실행:

```bash
python src/main.py \
  --input data/input.txt \
  --output data/output/graph_annotation.json \
  --ttl-output data/output/metaphors.ttl \
  --kg-output data/output/metaphor_kg.ttl
```

전처리/사전 lookup만 따로 실행:

```bash
python src/preprocessing/main.py --full
```

KG만 기존 annotation JSON에서 다시 생성:

```bash
python src/graph_build.py \
  --input data/output/graph_annotation.json \
  --output data/output/metaphor_kg.ttl
```

## Active Source Layout

- `src/main.py`: 공식 full pipeline entry point
- `src/preprocessing/`: sentence/POS/lemma/contextual/dictionary preprocessing
- `src/nodes/mipvu_judge.py`: lemma 단위 MIPVU LLM 판정
- `src/nodes/rdf_mapping.py`: MIPVU annotation을 KG mapping으로 변환
- `src/nodes/validation_check.py`: rule-based validation
- `src/nodes/rdf_convert.py`: state의 RDF mapping을 Turtle 문자열로 변환
- `src/rdf/convert.py`: deterministic RDF mapping/Turtle 변환 유틸
- `src/graph_build.py`: RDFLib graph build/serialize
- `src/prompts/`: 현재 pipeline에서 쓰는 프롬프트만 보관

## Removed Legacy Surface

아래 경로는 현재 pipeline과 분리되어 제거되었습니다.

- candidate 단위 prompt/staged pipeline
- old LangGraph `annotation_graph`
- `PromptAnnotator` / `FineTunedAnnotator`
- fine-tuning scripts, model config, finetune datasets
- legacy prompt files: `candidate_extract.md`, `mipvu_judge.md`, `metaphor_classify.md`, `annotation_schema.md`, `rdf_mapping.md`, `validation_check.md`
- head40/test/old Korean-named output artifacts

## Test

```bash
python -m pytest
```
