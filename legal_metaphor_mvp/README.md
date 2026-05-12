# legal_metaphor_mvp

한국어 법률 텍스트 은유 주석 MVP입니다.

핵심 원칙:
- 공식 실행 경로는 `src/main.py`의 기본 `full` 파이프라인입니다.
- `PromptAnnotator`와 `legacy-simple`는 개발/레거시 경로입니다.
- `finetuned`는 실험용(experimental) 백엔드입니다.
- 현재 MIPVU 판정 단위는 lemma group입니다.
- RDF/KG mapping, Turtle 변환, RDFLib graph build는 모두 결정적(deterministic) 경로를 사용합니다.
- LLM은 lemma-level MIPVU 판단에만 필요합니다. KG 생성 자체는 기존 JSON만으로 수행됩니다.

## Quick Start (실행 방법)

아래 명령은 모두 `legal_metaphor_mvp` 루트에서 실행합니다.

1. 가상환경/의존성 설치

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. 환경변수 파일 준비

```powershell
copy .env.example .env
```

`.env`에서 필요한 값 설정:
- `OPENAI_API_KEY` (LLM 연동 시)
- `STDICT_API_KEY` (표준국어대사전 연동 시, 없으면 안전 fallback)

3. 입력 텍스트 준비
- `data/input.txt`에 분석할 한국어 법률 텍스트 입력

4. 전체 파이프라인 실행

raw text에서 POS, lemma 정리, contextual JSON, dictionary lookup, lemma-level MIPVU,
RDF/Turtle, RDFLib KG까지 한 번에 실행합니다.

```bash
.venv/bin/python src/main.py
```

기본 입력/출력:
- 입력: `data/input.txt`
- annotation JSON: `data/output/graph_annotation.json`
- Turtle: `data/output/metaphors.ttl`
- RDFLib KG: `data/output/metaphor_kg.ttl`
- 중간 산출물: `data/output/pos_nodes*.json`, `data/output/lemma_dictionary_lookup.json`

`OPENAI_API_KEY`가 없으면 contextual meaning과 MIPVU LLM 단계는 fallback/reuse 경로로 처리되어
끝까지 실행되지만, 의미 있는 MRW/KG triple은 생성되지 않을 수 있습니다.

5. 기존 산출물 기반 graph 실행

실행 전에 `data/output/pos_nodes_contextualized.json`과
`data/output/lemma_dictionary_lookup.json`이 준비되어 있어야 합니다.

```powershell
python src/main.py --input data/input.txt --output data/output/graph_annotation.json --pipeline graph --ttl-output data/output/metaphors.ttl
```

동료 전처리 파이프라인에서 생성한 contextualized JSON을 사용하려면 다음처럼 입력:

```powershell
python src/main.py --input data/input.txt --output data/output/graph_annotation.json --pipeline graph --contextual-json data/output/pos_nodes_contextualized.json
```

전처리된 `pos_nodes_contextualized.json`은 문맥 의존 토큰 후보를 직접 만들며, graph 파이프라인은 이를 그대로 받아서 사전 비교 + LLM 판정에 들어갑니다.

6. 지식그래프 빌드(RDFLib)

```bash
.venv/bin/python src/graph_build.py \
  --input data/output/graph_annotation.json \
  --output data/output/metaphor_kg.ttl
```

입력은 annotation JSON 또는 Turtle 모두 가능합니다. KG 생성은 LLM을 사용하지 않습니다.

7. 레거시 단계형 주석 실행 (개발용)

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator prompt --pipeline staged
```

개발용 빠른 실행이 필요하면 `--pipeline legacy-simple`를 사용할 수 있습니다.

8. 선택: 실험용 파인튜닝 백엔드 추론 실행

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator finetuned
```

9. 독립 RDF 변환(항상 결정적 변환)

```powershell
python src/rdf_convert.py --input data/output/metaphors_raw.json --output data/output/metaphors.ttl
```

## Official Pipeline

전체 실행 경로는 `--pipeline full`, 기존 산출물 기반 주석 실행 경로는 `--pipeline graph`입니다.

흐름:
1. POS/lemma group 생성:
   - `data/input.txt` -> `pos_nodes.json`
2. lemma group sanity cleanup:
   - `pos_nodes.json` -> `pos_nodes_corrected.json`
3. contextual meaning 생성 또는 fallback/reuse:
   - `pos_nodes_corrected.json` -> `pos_nodes_contextualized.json`
4. lemma dictionary lookup:
   - `pos_nodes_contextualized.json` -> `lemma_dictionary_lookup.json`
5. 후보 로드:
   - `--contextual-json`의 `lemma_groups`에서 lemma occurrence를 후보로 생성
6. lemma dictionary lookup 결과 로드:
   - `data/output/lemma_dictionary_lookup.json`
7. lemma-level MIPVU judgment:
   - `mipvu_annotations` 생성
   - `source_domain`, `target_domain`, `conceptual_metaphor`, `lakoff_johnson_type` 포함
8. RDF/KG mapping (rule-based):
   - `mipvu_annotations`를 우선 사용
   - `metaphor_annotations`는 legacy fallback
9. validation (rule-based)
10. deterministic Turtle conversion
11. optional RDFLib graph build

출력 JSON에는 최소한 다음이 포함됩니다.
- `document_id`
- `case_id`
- `candidates`
- `mipvu_annotations`
- `metaphor_annotations`
- `rdf_mappings`
- `validation_results`
- `human_review_items`
- `rdf_output`
- `errors`
- `metadata`

### Lemma-level MIPVU Output

현재 `mipvu_annotations`의 핵심 필드는 다음과 같습니다.

- `lemma_group_id`
- `lemma`
- `contextual_meaning`
- `selected_sup_no`
- `original_meaning`
- `meaning_contrast`
- `distinctness`
- `comparison_possible`
- `similarity`
- `mipvu_label`
- `source_domain`
- `target_domain`
- `conceptual_metaphor`
- `lakoff_johnson_type`
- `confidence`
- `needs_human_review`

`pos`, `candidate_id`, `sentence_id`, `token`, `target_concept`, `source_concept`는 현재 lemma-level 출력 계약에 포함하지 않습니다.

### KG Layers

KG에는 다음 층위를 포함합니다.

| 층위 | JSON 필드 | RDF predicate 예시 |
| --- | --- | --- |
| MIPVU 식별 라벨 | `mipvu_label`, `mipvu_subtype`, `judgment_reason` | `ex:hasMIPVULabel` |
| source domain | `source_domain` | `ex:hasSourceDomain`, `ex:hasSourceDomainLabel` |
| target domain | `target_domain` | `ex:hasTargetDomain`, `ex:hasTargetDomainLabel` |
| conceptual metaphor | `conceptual_metaphor` | `ex:realizesConceptualMetaphor`, `ex:hasConceptualMetaphorLabel` |
| 고전적 유형 | `lakoff_johnson_type` | `ex:hasMetaphorType` |

예:

```text
MIPVU 식별 라벨      MRW_INDIRECT
source domain       BUILDING / PHYSICAL STRUCTURE
target domain       ARGUMENT / LEGAL REASONING
conceptual metaphor ARGUMENT IS A STRUCTURE
고전적 유형          STRUCTURAL
```

## Staged annotation process (legacy prompt pipeline)

이 경로는 기존 프롬프트 기반 실험 경로이며 candidate 추출 LLM 노드(`candidate_extract`)를 사용합니다.

`--annotator prompt --pipeline staged` 흐름:

1. 후보 추출 (`src/prompts/candidate_extract.md`)
   - 이 단계 내부에서 형태소/품사 태깅과 예외 후보 플래그를 함께 생성
2. 표준국어대사전 API 기본 의미 조회(가능 시)
3. MIPVU-informed 판정 (`src/prompts/mipvu_judge.md`)
4. 최종 은유 분류 (`src/prompts/metaphor_classify.md`)

기본 의미 판단 규칙:
- `STDICT_API_KEY`가 있으면 표준국어대사전 API로 basic meaning 후보를 조회합니다.
- API 키가 없거나 조회 실패 시, basic meaning은 LLM 또는 rule-based fallback에서 `inferred` 또는 `unavailable`로 처리합니다.
- 판단이 어려우면 `basic_meaning_source`는 `unavailable`로 남깁니다.
- 별도 단어 의미 중의성 해소 모듈은 사용하지 않습니다.

사전 API 키가 없으면 프로그램은 크래시하지 않고, 사전 조회 결과를 안전한 fallback payload로 반환합니다.
OpenAI API 키가 없으면 프로그램은 크래시하지 않고, `metadata.llm_available=false`와 `errors`에 이유를 남깁니다.

## Prompt Directory

공식 프롬프트 위치는 `src/prompts/`입니다.

현재 lemma-level MIPVU 흐름에서 사용하는 파일:
- `src/prompts/lemma_group_sanity.md` (optional preprocessing GPT)
- `src/prompts/contextual_meaning.md` (optional preprocessing GPT)
- `src/prompts/system_role.md`
- `src/prompts/korean_legal_mipvu_guideline.md`
- `src/prompts/lemma_mipvu_judge.md`

legacy/staged 경로에서 쓰이는 파일:
- `src/prompts/candidate_extract.md` (legacy staged path only)
- `src/prompts/mipvu_judge.md`
- `src/prompts/metaphor_classify.md`
- `src/prompts/annotation_schema.md`

`src/prompts/rdf_mapping.md`와 `src/prompts/validation_check.md`는 현재 그래프 파이프라인에서 직접 호출되지 않습니다.
프롬프트 호출 순서는 `src/prompts/PROMPT_ORDER.txt`에 정리되어 있습니다.

## Prompt Architecture (그래프 운영 기준)

- 현재 lemma-level KG 흐름에서 LLM 프롬프트가 개입되는 노드: `mipvu_judge`
- 규칙 기반으로 처리되는 노드: `rdf_mapping`, `validation_check`, `rdf_convert`
- RDFLib 기반 로컬 KG 빌더: `src/graph_build.py`
- 운영 기준에서 프롬프트는 다음에만 수정하면 됩니다.
  - contextual meaning 규칙 반영: `contextual_meaning.md`
  - lemma-level MIPVU/basic meaning/domain/KG 라벨 규칙 반영: `lemma_mipvu_judge.md`

주의: `metaphor_classify`는 아직 candidate 계약 기반 legacy 분류 단계입니다.
현재 KG 생성은 `mipvu_annotations`에서 직접 수행되므로 `metaphor_classify` 출력에 의존하지 않습니다.

## Legacy And Experimental Paths

- `--pipeline staged`: 레거시 prompt 경로
- `--pipeline legacy-simple`: 개발용 단순 경로
- `--annotator finetuned`: 실험용 백엔드이며 기본값이 아닙니다.

상세한 프롬프트 운영 아키텍처는 [docs/prompt-architecture.md](docs/prompt-architecture.md)에서 확인하세요.

## Fine-tune 보조 스크립트

`src/finetune/`와 `data/finetune/`는 실험용(experimental) 영역입니다.

```powershell
python src/finetune/prepare_dataset.py --input data/annotations/gold.jsonl --out-dir data/finetune
python src/finetune/train_annotation_model.py --train data/finetune/train.jsonl --valid data/finetune/valid.jsonl
python src/finetune/infer_annotation_model.py --input data/input.txt --output data/output/metaphors_finetuned.json
```

## 환경 변수

`.env.example`:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `STDICT_API_KEY` (optional)
- `STDICT_API_URL` (default: `https://stdict.korean.go.kr/api/search.do`)
- `STDICT_PAGE_SIZE` (default: `100`, lemma 사전 전체 검색 페이지 크기)

실제 LLM 주석을 실행하려면 `.env`에 `OPENAI_API_KEY`를 설정해야 합니다.
표준국어대사전 기본 의미 비교까지 쓰려면 `STDICT_API_KEY`도 설정합니다.

## 전처리 전용 파이프라인(동료 모듈 병합)

동료가 만든 형식상분석/동사형 추출/문맥의미 보정 파이프라인을 별도 모듈로 통합했습니다.
`src/preprocessing/` 폴더에서 실행할 수 있습니다.

### 설치

```powershell
pip install -r requirements.txt
```

### 기본 실행

```powershell
python src/preprocessing/main.py --full
```

`data/input.txt`를 읽어 다음 산출물을 생성합니다.
- `data/output/pos_nodes.json`
- `data/output/pos_nodes_corrected.json` (+ report)
- `data/output/pos_nodes_contextualized.json` (+ report)
- `data/output/lemma_dictionary_lookup.json` (`--full` 실행 시)

### 옵션

- `--input`: 입력 텍스트 경로
- `--output`: 1차 POS 결과 경로
- `--lemma-sanity`: 로컬 정제만 수행
- `--lemma-sanity-gpt`: GPT 정제 포함
- `--contextual-meaning`: 문맥적 의미 생성
- `--no-resume` / `--*.no-resume`: 캐시 무시하고 GPT 재요청
- `--dictionary-lookup`: `lemma_groups`의 모든 lemma를 표준국어대사전 API로 조회해 별도 JSON 생성
- `--dictionary-output`: 사전 조회 JSON 출력 경로
- `--dictionary-page-size`: 사전 검색 페이지 크기(기본 `STDICT_PAGE_SIZE` 또는 100)

이미 생성된 contextualized JSON만 대상으로 사전 조회를 실행하려면:

```powershell
python src/preprocessing/main.py --dictionary-lookup --contextual-output data/output/pos_nodes_contextualized.json
```

### 참고

이 전처리 파이프라인은 기존 `graph`/`staged` 공식 은유 판정 파이프라인과는 별도 단계입니다.
`graph` 공식 경로에서는 `--contextual-json` 입력 시 lemma별 `contextual_meaning`을 먼저 dictionary lookup과 병렬 비교해 반영한 뒤, LLM이 최종 판정에 참여합니다.
필요 시 `src/preprocessing/contextual_meaning.md`와 `src/prompts/lemma_group_sanity.md`를 수정해 실험할 수 있습니다.
