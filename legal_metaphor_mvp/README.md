# legal_metaphor_mvp

한국어 법률 텍스트 은유 주석 MVP입니다.

핵심 원칙:
- 기본 주석 백엔드는 `prompt`입니다.
- `finetuned`는 선택 백엔드입니다.
- RDF 변환은 항상 결정적(deterministic)이며 주석 백엔드와 분리됩니다.

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
2. 후보 형태소/품사 태깅 + 예외 후보 플래그
3. 표준국어대사전 API 기본 의미 조회(가능 시)
4. MIPVU-informed 판정 (`02_mipvu_judge.txt`)
5. 최종 은유 분류 (`03_metaphor_classify.txt`)

사전 API 키가 없으면 프로그램은 크래시하지 않고, 사전 조회 상태를 `no_api_key`로 처리합니다.

## Fine-tuning separation

- 파인튜닝은 기본 파이프라인의 일부가 아닙니다.
- 파인튜닝은 annotation 백엔드 대체 목적입니다.
- 출력 포맷은 동일한 canonical JSON(`{"metaphors":[...]}`)입니다.
- 따라서 `validate_schema` / `rdf_convert`는 변경 없이 동일하게 사용합니다.

## 실행 예시

```powershell
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator prompt --pipeline simple
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator prompt --pipeline staged
python src/main.py --input data/input.txt --output data/output/metaphors_raw.json --annotator finetuned
python src/rdf_convert.py --input data/output/metaphors_raw.json --output data/output/metaphors.ttl
python src/finetune/prepare_dataset.py --input data/annotations/gold.jsonl --out-dir data/finetune
python src/finetune/infer_annotation_model.py --input data/input.txt --output data/output/metaphors_finetuned.json
```

## 환경 변수

`.env.example`:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `STDICT_API_KEY` (optional)
- `STDICT_API_URL` (default: `https://stdict.korean.go.kr/api/search.do`)

## 환경 준비

Python 3.10+ 권장.

```powershell
cd legal_metaphor_mvp
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

