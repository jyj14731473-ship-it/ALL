# legal_metaphor_mvp

한국어 법률 텍스트 은유 주석 MVP입니다.

핵심 원칙:
- 기본 주석 백엔드는 `prompt`입니다.
- `finetuned`는 선택 백엔드입니다.
- RDF 변환은 항상 결정적(deterministic)이며 주석 백엔드와 분리됩니다.

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

4. 주석 실행 (기본: prompt/simple)

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator prompt --pipeline simple
```

5. 단계형 주석 실행 (후보추출→사전비교→MIPVU→분류)

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator prompt --pipeline staged
```

연구용으로는 `staged` 실행을 권장합니다. 각 단계의 중간 결과는 `stage_outputs`에 함께 저장됩니다.

6. 선택: 파인튜닝 백엔드 추론 실행

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator finetuned
```

7. RDF 변환(항상 결정적 변환)

```powershell
python src/rdf_convert.py --input data/output/metaphors_raw.json --output data/output/metaphors.ttl
```

## Annotation backends

- `prompt` (default):
  - 분리된 프롬프트(`prompts/`)를 사용
  - `simple`, `staged` 파이프라인 지원
- `finetuned` (optional):
  - `models/ft_model_config.json` 기반
  - 명시적으로 `--annotator finetuned`일 때만 동작

## Staged annotation process (MIPVU + dictionary comparison)

`--annotator prompt --pipeline staged` 흐름:

1. 후보 추출 (`01_candidate_extract.txt`)
   - 이 단계 내부에서 형태소/품사 태깅과 예외 후보 플래그를 함께 생성
2. 표준국어대사전 API 기본 의미 조회(가능 시)
3. MIPVU-informed 판정 (`02_mipvu_judge.txt`)
4. 최종 은유 분류 (`03_metaphor_classify.txt`)

사전 API 키가 없으면 프로그램은 크래시하지 않고, 사전 조회 상태를 `no_api_key`로 처리합니다.
OpenAI API 키가 없으면 LLM 주석 단계는 빈 결과(`{"metaphors":[]}`)로 안전하게 종료됩니다.

## Fine-tuning separation

- 파인튜닝은 기본 파이프라인의 일부가 아닙니다.
- 파인튜닝은 annotation 백엔드 대체 목적입니다.
- 출력 포맷은 동일한 canonical JSON(`{"metaphors":[...]}`)입니다.
- 따라서 `validate_schema` / `rdf_convert`는 변경 없이 동일하게 사용합니다.

## 프롬프트 구조

- `00_system_role.txt`: 시스템 역할/보수적 정책
- `01_candidate_extract.txt`: 은유 후보 추출 + 태깅/예외 후보
- `02_mipvu_judge.txt`: MIPVU-informed 판정
- `03_metaphor_classify.txt`: 최종 분류
- `04_annotation_schema.txt`: 표준 스키마 레퍼런스
- `05_korean_legal_mipvu_guidelines.txt`: 한국어 법률 텍스트용 MIPVU 적용 지침
- `06_validation_check.txt`: 검증 체크 규칙

## Fine-tune 보조 스크립트

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
