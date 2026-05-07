# PORORO Korean WSD Setup

PORORO는 오래된 Python/PyTorch 계열 의존성과 충돌할 수 있으므로 기본 `requirements.txt`에 넣지 않는다.
WSD 실험이 필요할 때만 별도 conda 환경에서 실행한다.

## 설치

```powershell
conda env create -f envs/pororo-wsd.yml
conda activate pororo-wsd
python scripts/test_pororo_wsd.py
```

## 실패 시 대안

- Python 3.8 conda 환경을 사용한다.
- Docker로 PORORO 실행 환경을 격리한다.
- PORORO 대신 LLM + 표준국어대사전 API 기반 임시 WSD를 사용한다.

## MIPVU 파이프라인에서의 역할

WSD는 문맥상 단어의 sense 후보를 추정하는 보조 도구다. 은유 판정 자체를 대신하지 않는다.
MIPVU 단계에서는 contextual meaning, basic meaning, distinctness, similarity 판단 중 contextual sense 추정 또는 distinctness 보조에 사용한다.
