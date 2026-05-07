# models

이 디렉터리는 **선택적(optional) 파인튜닝 모델 설정/메타데이터**를 저장합니다.

핵심 원칙:
- 기본 MVP는 `prompt` 기반 주석(annotator)을 사용합니다.
- 파인튜닝 모델은 기본 경로에 포함되지 않습니다.
- 파인튜닝 모델이 있더라도 교체 대상은 **annotation 모듈**뿐입니다.
  - candidate extraction
  - metaphor judgment
  - metaphor classification
- RDF 변환(`src/rdf_convert.py`)은 항상 결정적(deterministic) 로직이며, 파인튜닝 대상이 아닙니다.

주요 파일:
- `ft_model_config.json`: fine-tuned annotator 활성화 여부, provider, 모델명 등

