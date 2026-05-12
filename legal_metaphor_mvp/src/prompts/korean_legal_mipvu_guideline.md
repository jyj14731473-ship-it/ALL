# 한국어 법률 텍스트 MIPVU-informed 지침

목표:
- MIPVU의 Step 3a/3b/3c를 한국어 법률 텍스트에 맞게 보수적으로 모사한다.
- 과잉 은유 판정을 줄이고, 사람 검토가 필요한 후보를 명확히 표시한다.

분석 단위:
- 우선 어휘 단위(토큰/어절) 기준.
- 형태소가 해석에 필요할 때 `morphemes`에 기록.

Step 3a: Contextual Meaning(문맥 의미)
- 문장 내에서 해당 표현이 실제로 수행하는 기능/의미를 한 문장으로 설명한다.
- 법률 문맥에서의 기능(의무, 기준, 효력, 요건, 절차, 권리, 책임, 제한 등)을 함께 반영한다.

Step 3b: Basic Meaning(기본 의미)
- 가능한 한 사전/공식 용례 기준의 더 일반적/관용적 의미를 사용한다.
- 기본 의미를 안정적으로 제시할 수 없다면:
  - `basic_meaning_source: "unavailable"`
  - `basic_meaning: ""` 가능
  - 신뢰도는 낮추고 인적 검토 플래그를 켠다.

Step 3c: Distinctness / Similarity 판단
- `distinctness`: 문맥의미와 기본의미가 충분히 다른 개념인지.
- `comparison_possible`: 두 의미를 비교 가능한지.
- `similarity`: 외적/기능적/속성 유사성이 선명한지(은유적 대응이 있을 때).
- distinctness의 기준점은 사전 sense division이다. 사전에서 다른 numbered sense로 나뉠 수 있는 관계라면 충분히 distinct하다고 볼 수 있다.
- 사전이 하나의 numbered sense만 제공하면 그 sense를 basic sense로 삼고, 문맥 의미와 실제 기능/의미 차이가 있으면 그 차이를 sufficient distinctness로 취급할 수 있다.
- similarity는 class-inclusion, 단순 일반화, synecdoche가 아니다. 두 의미 사이에 현대 사용자 기준의 외적/기능적 resemblance가 보여야 한다.
- 역사적/어원적 연결만으로 MRW를 확정하지 않는다. 현대 사용자에게 투명한 similarity가 없으면 confidence를 낮추고 인적 검토 대상으로 둔다.

Indirect / Direct / Implicit MRW
- indirect MRW: 문맥 의미가 basic meaning에서 간접적으로 확장되고, distinctness와 similarity가 모두 충족되는 경우.
- direct MRW: source-domain 표현이 basic meaning 그대로 쓰이지만, local/main topic을 다른 domain으로 설명하는 nonliteral comparison으로 통합되는 경우.
- implicit MRW: 앞선 은유 표현이 새 source-domain 단어 없이 대명사, 지시어, 대용 표현, 일반어, 생략 등 cohesion device로 이어지는 경우.
- direct/implicit은 sample sentence 안에서 근거가 명확할 때만 확정한다. 근거가 부족하면 candidate 또는 human review로 둔다.

Lakoff & Johnson 고전적 유형론
- MRW 계열이면 conceptual mapping을 structural, orientational, ontological 중 하나로 분류한다.
- structural: 한 개념 영역의 구조가 다른 개념 영역을 조직적으로 이해하게 하는 경우.
- orientational: 위/아래, 안/밖, 앞/뒤, 중심/주변, 깊이/표면 등 공간 방향성이 추상 개념을 조직하는 경우.
- ontological: 추상 대상, 사건, 상태, 권리, 책임 등을 물체, 물질, 그릇, 행위자, 사람처럼 다루는 경우.
- personification, container, entity/substance 계열은 ontological의 세부 사례로 처리한다.
- 비은유이면 not_applicable, 판단 불가이면 uncertain으로 둔다.

Conceptual metaphor domain labels
- MRW 계열이면 target_domain, source_domain, conceptual_metaphor를 함께 제시한다.
- target_domain은 문맥에서 설명되는 법률/논리/사실/판단 영역이다.
- source_domain은 basic/original meaning에서 빌려온 이미지, 물리 영역, 구조, 행위 영역이다.
- conceptual_metaphor는 "TARGET IS SOURCE" 방향으로 쓴다. 예: ARGUMENT IS A STRUCTURE.

핵심 보수 규칙:
- 기본 의미와 문맥 의미가 서로 거의 같은 개념(사전 설명만 관점이 바뀐 수준)이라면 MRW로 판단하지 않는다.
- 유사성은 **명시적/기능적 대응**이 있을 때만 true.
- 법률 상투표현은 기본값으로 `distinctness=false`, `similarity=false`에 가깝게 처리.
- `needs_human_review`는 불확실성, 사전 근거 부재, 경계 케이스에서 항상 true.

주의 표현(우선 점검어):
- 부담하다, 성립하다, 소멸하다, 귀속되다, 관철하다, 배척하다, 흠결, 효력, 요건, 기초, 전제, 범위, 한계
- 위 단어는 즉시 비은유라고 단정하지 말고, “법적 관용성”을 고려해 추가 근거가 있을 때만 MRW로 올린다.
