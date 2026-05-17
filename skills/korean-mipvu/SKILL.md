---
name: korean-mipvu
description: Apply MIPVU to Korean legal judgment text. Use when identifying, validating, or explaining Korean lexical-unit-level metaphor candidates, especially when using KonLPy's Okt analyzer, Standard Korean Language Dictionary meanings, and OpenAI judgment for ALL_Metaphor.
---

# Korean MIPVU

## Overview

Use this skill to adapt MIPVU conservatively for Korean legal judgments. Keep the analysis evidence-based: preserve the original surface form, local context, dictionary meaning, and rationale for every candidate decision.

Read `references/mipvu_protocol.md` when implementing or revising the metaphor judgment procedure. Read `references/edge_cases.md` when changing filtering, ambiguity handling, or validation behavior.

## Workflow

1. Preserve word-level positions from the original judgment text for traceability.
2. Segment the judgment into word-level lexical units.
3. Use KonLPy's Okt analyzer to identify morphemes inside each word-level unit, especially nouns, verbs, adjectives, adverbs, particles, and endings.
4. Exclude Korean particles, endings, auxiliary-only forms, punctuation, numbers, and purely structural legal-document tokens unless there is explicit evidence that they carry metaphorical meaning.
5. For nouns with attached particles, use the content noun as the dictionary lookup key while preserving the original surface form in JSON evidence.
6. For verbs and adjectives, normalize to dictionary form before dictionary lookup where possible.
7. Query the Standard Korean Language Dictionary API for candidate meanings.
8. Compare contextual meaning and dictionary meaning according to MIPVU.
9. Ask the LLM to judge only filtered candidates with dictionary meanings and bounded local context.
10. Mark uncertain candidates as `unresolved` instead of forcing a metaphor decision.

## Korean-Specific Rules

- Treat legal terms of art as non-metaphorical by default when their contextual meaning matches conventional legal usage. A legal term may differ from a general dictionary meaning, but within the legal community its conventional legal meaning controls.
- Avoid false positives for ordinary legal jargon such as `권리의 성립`, `의무의 이행`, `성립`, and `이행`; otherwise almost every legal term with a more concrete or physical general meaning could be mislabeled as metaphorical.
- When the dictionary returns multiple senses, keep all plausible basic meanings and let the LLM compare them against the local legal context.
- Focus first on indirect metaphor: contextual meaning contrasts with a more basic dictionary meaning but can be understood by comparison.
- Mark candidates as `unresolved` when any unresolved criterion in `references/edge_cases.md` applies.
- Direct metaphor and implicit metaphor handling are TBD.
- Source-domain and target-domain labels should be added only when evidence supports them; otherwise leave them as `TBD` or omit them from RDF output.
- Use `metaphor_type` values only from `indirect`, `direct`, `implicit`, or `null`.

## Token Discipline

- Do not send full judgment text to the LLM.
- Send only filtered candidate lexical units with bounded local context.
- Use a local context window of `±N` tokens per lexical unit, with default `N=10` and maximum `N=30`.
- Never include more than 100 characters of local context per lexical unit.
- Include dictionary meanings so the LLM compares meanings instead of inventing basic meanings.
- Deduplicate repeated lemmas before dictionary lookup and LLM judgment.
