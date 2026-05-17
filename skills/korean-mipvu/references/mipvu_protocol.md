# MIPVU Protocol Reference

## Core Decision Flow

Use MIPVU at the lexical-unit level.

1. Identify the lexical unit in the original text.
2. Determine its contextual meaning in the local legal context.
3. Retrieve plausible dictionary meanings.
4. Identify a more basic meaning when available.
5. Decide whether the contextual meaning contrasts with the basic meaning.
6. Decide whether the contextual meaning can be understood by comparison with the basic meaning.
7. Mark the candidate as `metaphorical`, `non_metaphorical`, or `unresolved`.

## Korean Adaptation

- Preserve the original word-level surface form.
- Use KonLPy's Okt analyzer for internal morpheme and POS analysis.
- Use lemma or normalized dictionary form for dictionary lookup.
- Keep the original surface form, lemma, POS, local context, dictionary meanings, and rationale in intermediate JSON.
- Prefer `unresolved` when the contextual/basic meaning contrast is weak or not evidence-backed.

## Decision Labels

- `metaphorical`: Evidence supports a metaphor-related use.
- `non_metaphorical`: Contextual meaning matches a conventional or dictionary meaning without metaphorical comparison.
- `unresolved`: Evidence is insufficient, dictionary lookup returned no result, no clear basic meaning can be identified, contextual meaning cannot be paraphrased confidently, LLM confidence is below `0.5`, legal-domain ambiguity remains, dictionary lookup failed, or LLM validation failed.

## Metaphor Types

- `indirect`: Contextual meaning differs from basic meaning and is understood by comparison.
- `direct`: TBD.
- `implicit`: TBD.
- `null`: Use when not metaphorical or unresolved.
