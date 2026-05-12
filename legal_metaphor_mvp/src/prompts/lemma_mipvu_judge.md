# Lemma 단위 MIPVU original meaning 선택 및 비교

과업:
- 각 lemma마다 dictionary definitions 중 MIPVU 기준상 more basic meaning에 해당하는 original/basic meaning 하나를 고른다.
- 고른 original meaning을 contextual_meaning 및 sample_sentences와 1대1로 비교한다.
- 비교 결과에 따라 indirect, direct, implicit 가능성을 검토하고 MIPVU-informed 라벨을 부여한다.
- 은유 가능성이 있으면 target_domain, source_domain, conceptual_metaphor를 판단한다.
- 은유 가능성이 있으면 Lakoff & Johnson의 고전적 유형론 라벨도 부여한다.

중요 규칙:
- POS는 고려하지 않는다.
- dictionary definitions에 없는 original meaning을 새로 만들지 않는다.
- selected_sup_no는 반드시 입력 definitions 중 하나의 sup_no여야 한다.
- original_meaning은 선택한 definition 문장을 그대로 사용한다.
- contextual_meaning과 sample_sentences를 모두 근거로 삼는다.
- 은유 판단은 보수적으로 한다.
- target_domain/source_domain/conceptual_metaphor는 MRW, MRW_candidate, borderline_candidate일 때만 채운다.
- non_MRW 또는 uncertain이면 target_domain, source_domain, conceptual_metaphor, concept_mapping_reason은 빈 문자열로 둔다.
- mipvu_label은 반드시 MRW, MRW_candidate, borderline_candidate, non_MRW, uncertain 중 하나만 쓴다.
- direct/indirect/implicit 하위 유형은 별도 라벨로 만들지 말고 judgment_reason에 명시한다.
- lakoff_johnson_type은 반드시 structural, orientational, ontological, not_applicable, uncertain 중 하나만 쓴다.
- non_MRW이면 lakoff_johnson_type은 not_applicable로 둔다.
- uncertain이면 lakoff_johnson_type은 uncertain으로 둔다.
- 출력은 JSON object 하나만 허용한다. Markdown, 코드블록, 설명문 금지.

more basic meaning 선택 기준:
- MIPVU의 basic meaning은 무조건 어원상 최초 의미가 아니다.
- 입력 dictionary definitions 안에 있는 현대 일반 사용자 사전 의미 중에서 고른다.
- dictionary definitions에 없는 의미는 basic/original meaning으로 삼지 않는다.
- 우선순위는 다음과 같다.
  1. contextual meaning보다 더 concrete한 의미.
  2. contextual meaning보다 더 specific한 의미.
  3. contextual meaning보다 더 human-oriented, bodily, sensory, social interaction에 가까운 의미.
  4. 여러 뜻이 모두 가능하면, sample_sentences의 쓰임과 비교 가능한 뜻.
- contextual meaning이 전문적이거나 추상적인 법률 의미이고 dictionary definitions 안에 더 일반적이고 concrete한 의미가 있으면, 그 concrete한 뜻을 basic meaning으로 우선 선택한다.
- 어떤 concrete sense가 전문 분야에 제한되어 있어도, contextual meaning보다 더 concrete하고 dictionary definitions에 존재하면 basic meaning 후보가 될 수 있다.
- 반대로 contextual meaning과 거의 같은 일반 추상 의미밖에 dictionary definitions에 없다면, 그 뜻을 선택하되 distinctness를 낮게 판단한다.
- 예: 종교적 father/mother 용법보다 일반적 가족관계 의미가 더 basic하다.
- 예: "argument collapsed"에서 collapsed의 contextual meaning은 "논증이 설득력을 잃다"이고, basic meaning은 사전에 있는 물리적 붕괴 의미 쪽이다.

distinctness 판단 기준:
- 판정의 기준점은 dictionary definitions의 sense division이다.
- contextual meaning과 original/basic meaning이 사전에서 서로 다른 numbered sense로 나뉠 수 있는 관계라면 sufficiently distinct하다고 본다.
- dictionary definitions가 하나의 numbered sense만 제공하면, 그 sense를 basic sense로 삼는다. 이때 sample_sentences의 contextual meaning이 그 sense와 실제 기능/의미에서 차이를 보이면 그 차이를 sufficient distinctness로 취급할 수 있다.
- contextual meaning이 selected original meaning과 거의 같은 뜻이고 표현 방식만 다른 정도라면 distinctness=false에 가깝다.

similarity 판단 기준:
- 두 의미가 다르기만 하면 MRW가 아니다. contextual meaning이 original/basic meaning과 external resemblance 또는 functional resemblance로 연결되어야 한다.
- similarity는 풍부할 필요가 없다. 매우 schematic한 기능적 유사성도 가능하다.
- 예: "물리적으로 지탱하다"와 "논리적으로 지탱하다" 사이의 기능적 대응은 similarity=true가 될 수 있다.
- similarity는 class-inclusion, 단순 일반화, synecdoche와 다르다.
- 법률적 concrete sense와 일반 abstract sense가 단순 일반화 관계라면 metaphor가 아니라 synecdoche/비은유일 수 있다.
- 반대로 "physical pain을 완화하다"에서 "bad situation을 완화하다"처럼 concrete-to-abstract 기능 유사성이 투명하면 MRW indirect가 될 수 있다.
- 두 의미가 역사적으로 연결되어 보이더라도 현대 일반 사용자에게 투명한 유사성이 보이지 않으면 은유로 밀어붙이지 않는다. 이 경우 non_MRW, borderline_candidate, 또는 needs_human_review=true로 처리한다.
- OED 같은 역사 사전 확인이 필요해 보이나 현재 입력만으로 확인할 수 없으면, 어원상 연결만으로 MRW를 확정하지 말고 confidence를 낮추고 needs_human_review=true로 둔다.

indirect metaphor 판단 기준:
- lemma의 contextual meaning이 original/basic meaning에서 간접적으로 확장되어 쓰였고,
  distinctness=true 및 similarity=true이면 MRW indirect로 판단할 수 있다.
- 출력 스키마에는 하위 유형 필드가 없으므로 mipvu_label은 MRW로 두고 judgment_reason에 "indirect"라고 적는다.

direct metaphor 판단 기준:
- direct metaphor는 source-domain 단어가 original/basic meaning 그대로 등장하지만, 담화의 topic/referent를 설명하기 위해 다른 domain으로 끌려오는 경우다.
- 다음 네 조건을 순서대로 점검한다.
  1. sample_sentences 안에서 local referent/topic shift가 있는가.
  2. 주변 텍스트와 어울리지 않는 incongruous lexical unit이 전체 referential/topic framework 안에 comparison을 통해 통합되는가.
  3. 그 comparison이 literal comparison이 아니라 nonliteral 또는 cross-domain comparison인가.
  4. source-domain 표현이 local/main topic에 대한 indirect discourse로 기능하는가.
- 조건 2-4가 positive이면 MRW direct로 판단할 수 있다.
- 예: "The lawyer was a bulldog"에서 bulldog은 개라는 basic meaning 그대로이지만, 실제 topic은 lawyer이고 동물 domain이 사람 평가에 투사되므로 MRW direct다.
- 반대로 "The campsite was like a holiday village"처럼 두 대상이 같은 넓은 domain 안에서 literal comparison으로 볼 수 있으면 direct metaphor가 아닐 수 있다.
- 핵심은 두 concepts가 문맥상 distinct and contrasted domains로 구성될 수 있는지다.
- 출력 스키마에는 하위 유형 필드가 없으므로 mipvu_label은 MRW로 두고 judgment_reason에 "direct"라고 적는다.

implicit metaphor 판단 기준:
- implicit metaphor는 source-domain 단어가 새로 나오지 않고, 앞선 은유 표현을 대명사, 지시어, 대용 표현, 일반어, 생략 등이 이어받는 경우다.
- 먼저 해당 form이 실제 cohesion device로 쓰였는지 판단한다.
- 다음으로 그 cohesion device가 앞서 metaphor-related로 표시될 수 있는 word/concept와 연결되는지 본다.
- 연결이 명확하면 MRW implicit로 판단할 수 있다.
- demonstrative/general word가 자체적으로 indirect metaphor이면서 동시에 앞의 은유를 받으면 judgment_reason에 결합 가능성을 적고 needs_human_review=true로 둔다.
- tag question처럼 대체 가능한 full expression을 안정적으로 복원할 수 없는 경우는 cohesion으로 보지 않는다.
- 현재 입력에는 이전 MRW annotation 목록이 없으므로, sample_sentences 안에서 앞선 은유 표현과 cohesion 관계가 명확할 때만 implicit을 확정한다. 불명확하면 MRW_candidate, borderline_candidate, 또는 uncertain으로 둔다.
- 출력 스키마에는 하위 유형 필드가 없으므로 mipvu_label은 MRW로 두고 judgment_reason에 "implicit"이라고 적는다.

Lakoff & Johnson 유형론 라벨 기준:
- 이 라벨은 MIPVU 라벨이 MRW, MRW_candidate, borderline_candidate일 때만 실질적으로 부여한다.
- structural: 한 개념 영역의 구조가 다른 개념 영역을 조직적으로 이해하게 하는 경우. 예: 논쟁/법적 판단을 전쟁, 건축, 여정, 계산, 기계 작동 같은 구조로 파악하는 경우.
- orientational: 위/아래, 안/밖, 앞/뒤, 중심/주변, 깊이/표면, 가까움/멀어짐 같은 공간적 방향성이 추상 개념을 조직하는 경우.
- ontological: 사건, 상태, 감정, 책임, 권리, 법적 관계 같은 추상 대상을 물체, 물질, 그릇, 소유물, 행위자, 사람처럼 다루는 경우.
- personification, container metaphor, entity/substance metaphor는 별도 라벨을 만들지 말고 ontological로 분류하고 lakoff_johnson_type_reason에 세부 근거를 적는다.
- 하나의 사례가 여러 유형처럼 보이면 문맥에서 가장 중심적인 mapping을 하나만 고른다.
- 유형 판단 근거가 약하지만 은유 가능성은 있으면 lakoff_johnson_type은 uncertain으로 두고 needs_human_review=true로 둔다.

conceptual metaphor 라벨 기준:
- conceptual_metaphor는 target_domain과 source_domain의 관계를 "TARGET IS SOURCE" 형식으로 압축한 라벨이다.
- 가능하면 영어 대문자 도메인 라벨을 사용한다. 예: ARGUMENT IS A STRUCTURE, LEGAL REASONING IS PHYSICAL SUPPORT.
- 영어 라벨이 어색하거나 과도하게 추상적이면 한국어 명사구를 사용해도 된다. 단, target과 source의 방향은 분명해야 한다.
- target_domain은 문맥에서 실제로 말하려는 법률/논리/사실/판단 영역이다.
- source_domain은 original/basic meaning 쪽에서 빌려온 이미지, 영역, 구조다.
- conceptual_metaphor는 target_domain을 먼저, source_domain을 나중에 둔다.
- non_MRW 또는 uncertain에서는 conceptual_metaphor를 빈 문자열로 둔다.

출력 필드별 판정 기준:
- comparison_possible: original_meaning과 contextual_meaning을 비교할 수 있으면 true.
- distinctness: 두 의미가 개념적으로 충분히 다르면 true.
- similarity: 다르지만 어떤 기능적/구조적/속성적 대응이 선명하면 true.
- target_domain: 원관념 domain. 문맥에서 실제로 말하려는 법률/사실/판단/논리 영역.
- source_domain: 보조관념 domain. original meaning 쪽에서 빌려온 이미지, 영역, 구조.
- conceptual_metaphor: target_domain과 source_domain의 관계를 "TARGET IS SOURCE" 형식으로 압축한 라벨.
- concept_mapping_reason: target_domain과 source_domain을 그렇게 본 근거.
- lakoff_johnson_type: structural, orientational, ontological, not_applicable, uncertain 중 하나.
- lakoff_johnson_type_reason: Lakoff & Johnson 유형론 라벨을 고른 짧은 이유.
- mipvu_label:
  - MRW: distinctness와 similarity가 모두 선명하고 은유 관련 단어로 볼 수 있음.
  - MRW_candidate: 은유 가능성이 있으나 확정 전 검토가 필요함.
  - borderline_candidate: 경계 사례.
  - non_MRW: 은유 아님.
  - uncertain: 정보 부족 또는 판단 보류.

입력:
{{LEMMA_BATCH_JSON}}

출력 형식:
{
  "judgments": [
    {
      "lemma_group_id": "lg001",
      "lemma": "입력 lemma 그대로",
      "contextual_meaning": "입력 contextual_meaning 그대로",
      "selected_sup_no": "선택한 사전 뜻의 sup_no",
      "original_meaning": "선택한 definition 그대로",
      "original_meaning_selection_reason": "해당 뜻을 고른 짧은 이유",
      "meaning_contrast": "original meaning과 contextual meaning의 같고 다른 점",
      "distinctness": false,
      "comparison_possible": true,
      "similarity": false,
      "target_domain": "",
      "source_domain": "",
      "conceptual_metaphor": "",
      "concept_mapping_reason": "",
      "lakoff_johnson_type": "not_applicable",
      "lakoff_johnson_type_reason": "",
      "mipvu_label": "non_MRW",
      "judgment_reason": "최종 라벨 판단 이유",
      "confidence": 0.0,
      "needs_human_review": false,
      "occurrence_count": 0,
      "sample_sentences": []
    }
  ]
}
