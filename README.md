# ALL_Metaphor

## Overview

ALL_Metaphor는 `.txt` 형식의 한국어 법률 판결문을 입력으로 받아 MIPVU 방법론에 따라 개념적 은유를 식별하는 프로젝트입니다.
파이프라인은 어휘 단위별 근거를 보존하고, 중간 결과를 JSON으로 저장한 뒤, 검증된 은유 분석 결과를 RDF triples로 매핑합니다.
RDF 출력은 로컬 지식 그래프 활용을 위해 Turtle (`.ttl`) 형식으로 직렬화합니다.

## Project Status

- Phase 0: Complete
- Phase 1: Complete
- Phase 2: In Progress
- Phase 3: Planned

## Setup

Windows PowerShell에서 프로젝트 루트 기준으로 실행합니다.
Python 3.12가 필요합니다.
Python 3.12 가상환경을 만들고, 개발 의존성을 포함해 editable mode로 설치합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

환경변수 설정:

```powershell
Copy-Item .env.example .env
```

`.env` 파일을 열어 `OPENAI_API_KEY`, `OPENAI_MODEL`, `KRDICT_API_KEY`를 입력합니다.
`ALL_LOG_LEVEL`은 선택값이며 기본값은 `INFO`입니다.

설치 검증:

```powershell
ruff check src/
pytest
python -c "import openai, konlpy, rdflib, pydantic; print('OK')"
```

`ruff check src/`는 `All checks passed!`가 나오면 정상입니다.
`pytest`는 기본 단위 테스트가 모두 통과하면 정상입니다.
import 테스트는 `OK`가 출력되면 정상입니다.

## Usage

권장 실행 방식은 패키지 CLI입니다.
입력 `.txt`, intermediate JSON 출력 경로, Turtle RDF 출력 경로를 명시합니다.
루트 `main.py`는 같은 CLI를 호출하는 호환 wrapper입니다.

```powershell
python -m all_metaphor.cli --input data/input/example.txt --json-output outputs/intermediate/example.json --ttl-output outputs/rdf/example.ttl
python main.py --input data/input/example.txt --json-output outputs/intermediate/example.json --ttl-output outputs/rdf/example.ttl
```

## Commands

- 실행: `python -m all_metaphor.cli --input data/input/example.txt --json-output outputs/intermediate/example.json --ttl-output outputs/rdf/example.ttl`
- 호환 실행: `python main.py --input data/input/example.txt --json-output outputs/intermediate/example.json --ttl-output outputs/rdf/example.ttl`
- 테스트: `pytest`
- 통합 테스트: `pytest -m integration`
- 린트: `ruff check src/`
- 포맷: `ruff format src/`
- 타입 검사: `mypy src/`

## Known Issues

- KonLPy/JPype Windows 환경에서 실제 Okt/JVM을 호출하는 통합 테스트 실행 시 `fatal exception: access violation` 로그가 발생할 수 있습니다.
- 기본 `pytest` 실행은 `integration` 테스트를 제외하므로 Okt/JVM을 호출하지 않습니다.
- 실제 Okt smoke test는 `pytest -m integration`으로 명시 실행합니다.

## Project Structure

```text
.
├── AGENTS.md, pyproject.toml, main.py, README.md
├── src/all_metaphor/, tests/
├── data/input/, outputs/intermediate/, outputs/rdf/
└── skills/korean-mipvu/  # SKILL.md 및 references/
```

## Documentation

프로젝트 규칙과 제약은 `AGENTS.md`에 있습니다.
한국어 MIPVU 적용 규칙은 `skills/korean-mipvu/SKILL.md`에 있습니다.
세부 참고 자료는 `skills/korean-mipvu/references/`에 있습니다.
