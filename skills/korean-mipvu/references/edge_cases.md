# Korean MIPVU Edge Cases

## Exclude By Default

- Particles and endings.
- Punctuation and symbols.
- Numbers, dates, case numbers, article numbers, and paragraph markers.
- Pure legal boilerplate tokens.
- Auxiliary-only forms.
- Tokens with no plausible dictionary lookup key.

## Okt POS Filter

ALL_Metaphor uses KonLPy's Okt analyzer.

### Include As Metaphor Candidates

- `Noun`: general nouns.
- `Verb`: verbs.
- `Adjective`: adjectives.
- `Adverb`: adverbs, excluding mimetic and onomatopoeic forms by default.

### Always Exclude

- `Josa`: particles such as `이`, `가`, `을`, `를`, and `의`.
- `Eomi`: endings such as `는다`, `었다`, and `하지만`.
- `PreEomi`: pre-final endings.
- `Suffix`: suffixes.
- `Punctuation`: punctuation.
- `Number`: numbers.
- `Foreign`: foreign-language tokens by default unless explicitly meaningful in context.
- `Alpha`: alphabetic tokens.
- `Unknown`: unknown tokens.

### Conditional

- `Determiner`: usually exclude; review case by case only when semantically meaningful.
- `Conjunction`: exclude.
- `Exclamation`: exclude.

## Legal Terms Of Art

Treat legal terms of art as non-metaphorical by default when they are used in their conventional legal sense. Examples include `권리의 성립`, `의무의 이행`, `성립`, and `이행`.

Rationale: even when a term's general dictionary meaning is more concrete or physical, the legal community may already use it with a stable conventional legal meaning. In that case, the legal contextual meaning is not metaphorical merely because it differs from the general dictionary sense.

False-positive risk: if terms such as `성립` or `이행` are treated as metaphorical solely because their general dictionary meanings are more concrete, almost every legal term can become a metaphor candidate.

Mark as `unresolved` when a legal term appears to carry a broader conceptual comparison that is not directly supported by dictionary meanings.

## Multiple Dictionary Senses

Keep all plausible basic meanings in intermediate JSON. Do not collapse senses before LLM judgment unless they are exact duplicates.

## Attached Particles

For a surface form such as noun plus particle, preserve the full surface form in evidence but use the noun lemma as the dictionary query.

## Verbs And Adjectives

Normalize verbs and adjectives to dictionary form where possible. If normalization is uncertain, keep the surface form and record the uncertainty in the candidate errors.

## Context Window

Use `±10` tokens by default and never exceed `±30` tokens. The local context string for one lexical unit must not exceed 100 characters.

## Confidence

Confidence is the LLM-reported probability that the lexical unit is used metaphorically in the specific context. It must be in `[0.0, 1.0]`. The default RDF inclusion threshold is `0.5`, but the final threshold remains TBD.

## Unresolved Criteria

Mark a candidate as `unresolved` when any of the following applies:

- LLM confidence is less than `0.5`.
- Dictionary lookup returned no result.
- Multiple dictionary senses are available but no clear basic meaning can be identified.
- Contextual meaning cannot be paraphrased confidently.
- Legal-domain ambiguity remains because the term could be either conventional legal jargon or metaphorical usage.
