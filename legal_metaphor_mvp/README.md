# legal_metaphor_mvp

한국어 법률 텍스트 은유 주석 MVP입니다.

핵심 원칙:
- 공식 실행 경로는 `LangGraph` 기반 `graph` 파이프라인입니다.
- `PromptAnnotator`와 `legacy-simple`는 개발/레거시 경로입니다.
- `finetuned`는 실험용(experimental) 백엔드입니다.
- RDF mapping과 Turtle 변환은 항상 결정적(deterministic) 경로를 사용합니다.

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

4. 공식 주석 실행 (기본: graph)

```powershell
python src/main.py --input data/input.txt --output data/output/graph_annotation.json --pipeline graph --ttl-output data/output/metaphors.ttl
```

5. 레거시 단계형 주석 실행 (개발용)

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator prompt --pipeline staged
```

개발용 빠른 실행이 필요하면 `--pipeline legacy-simple`를 사용할 수 있습니다.

6. 선택: 실험용 파인튜닝 백엔드 추론 실행

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator finetuned
```

7. RDF 변환(항상 결정적 변환)

```powershell
python src/rdf_convert.py --input data/output/metaphors_raw.json --output data/output/metaphors.ttl
```

## Official Pipeline

공식 실행 경로는 `graph` 파이프라인입니다.

흐름:
1. candidate extraction
2. basic meaning lookup
3. MIPVU judgment
4. metaphor classification
5. RDF mapping (rule-based)
6. validation (rule-based)
7. deterministic Turtle conversion

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

## Staged annotation process (MIPVU + dictionary comparison)

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

사용 파일:
- `src/prompts/system_role.md`
- `src/prompts/candidate_extract.md`
- `src/prompts/mipvu_judge.md`
- `src/prompts/metaphor_classify.md`
- `src/prompts/annotation_schema.md`
- `src/prompts/korean_legal_mipvu_guideline.md`

`src/prompts/rdf_mapping.md`와 `src/prompts/validation_check.md`는 현재 그래프 파이프라인에서 직접 호출되지 않습니다.

## Prompt Architecture (그래프 운영 기준)

- LLM 프롬프트가 개입되는 노드: `candidate_extract`, `mipvu_judge`, `metaphor_classify`
- 규칙 기반으로 처리되는 노드: `rdf_mapping`, `validation_check`, `rdf_convert`
- 운영 기준에서 프롬프트는 다음에만 수정하면 됩니다.
  - 문장/표현 추출 품질 개선: `candidate_extract.md`
  - MIPVU 판정 규칙 반영: `mipvu_judge.md`
  - 은유 분류 규칙 반영: `metaphor_classify.md`

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

실제 LLM 주석을 실행하려면 `.env`에 `OPENAI_API_KEY`를 설정해야 합니다.
표준국어대사전 기본 의미 비교까지 쓰려면 `STDICT_API_KEY`도 설정합니다.
