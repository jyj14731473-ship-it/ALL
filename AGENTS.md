# AGENTS.md

## 1. Project Overview

ALL is a project for building ALL_Metaphor, an agent that takes `.txt` legal judgment documents as input, identifies conceptual metaphors based on the MIPVU methodology, and maps the resulting analysis into a knowledge graph using RDF triples.

## 2. Tech Stack

- Methodology: MIPVU
- Programming language: Python
- Python version: 3.12
- Input format: `.txt`
- Data representation: RDF triples
- RDF output format: Turtle (`.ttl`)
- Intermediate output format: JSON
- Knowledge representation target: Knowledge graph
- Execution environment: Local development in VS Code
- Runtime: Python 3.12
- LLM or NLP provider: OpenAI API
- OpenAI model source: Environment variable
- Dictionary meaning source: Standard Korean Language Dictionary API
- Dictionary API credentials source: Environment variable
- Morphological analyzer: KonLPy Okt
- Lexical-unit segmentation: Word-level segmentation
- RDF library: rdflib
- Graph database: Not required at this stage
- Storage: Local files
- UI or API framework: Not required at this stage
- Test framework: pytest
- Linter: ruff
- Formatter: ruff format
- Type checker: mypy (optional)
- Pipeline orchestration: LangGraph (deferred; add when `pipeline.py` is implemented)

### Approved Dependencies

Runtime:

- `openai`: OpenAI API client
- `konlpy`: Korean morphological analysis
- `rdflib`: RDF graph construction and Turtle serialization
- `pydantic`: schema validation for intermediate JSON and LLM responses
- `python-dotenv`: environment variable loading
- `langgraph`: pipeline orchestration (deferred; add when `pipeline.py` is implemented)

Development:

- `pytest`: tests
- `pytest-cov`: test coverage measurement
- `ruff`: linting and formatting
- `mypy`: optional static type checking

External library policy: Any dependency outside this list requires explicit approval. All dependencies must be pinned in `pyproject.toml`.

## 3. Hard Constraints

- Do not infer or invent requirements that the user has not explicitly approved.
- Mark unspecified implementation details as `TBD`.
- Do not add external libraries unless the user has explicitly approved them.
- Keep the initial folder structure simple; defer expansion until there is a concrete need.
- Before implementing each pipeline node listed in Pipeline Nodes, propose a short AS-IS vs TO-BE design.
- After implementing each pipeline node, add or update focused unit tests for that node and any touched helper module before moving to the next node.
- After any code change, run `ruff format src/ tests/` before committing.
- Before committing or handing off implementation work, run `ruff check src/` and `pytest`; both must pass unless a blocker is explicitly reported.
- Breaking changes to the intermediate schema or RDF vocabulary must bump `schema_version` until separate RDF vocabulary versioning is approved.
- Processing Pipeline and Pipeline Nodes sections must stay in sync.
- Preserve MIPVU as the conceptual metaphor identification methodology.
- Represent extracted knowledge graph facts as RDF triples.
- Treat `.txt` judgment documents as the primary input type.
- Do not assume that the source judgment exposes rich semantic relationships beyond what the analysis identifies.
- Prioritize stable mapping of MIPVU analysis results over complex relationship inference.
- Analyze metaphor candidates at the lexical-unit level.
- Use word-level lexical units as the primary analysis unit.
- Use KonLPy's Okt analyzer for Korean morphological analysis, part-of-speech filtering, and dictionary-form normalization.
- Reduce token usage by excluding particles, function words, and words that are clearly unlikely to be metaphor candidates before sending candidates to the LLM.
- Compare candidate lexical units against dictionary meanings from the Standard Korean Language Dictionary API before asking the LLM to judge metaphorical use.
- Save intermediate analysis outputs as JSON before producing RDF Turtle output.
- Read OpenAI model configuration and Standard Korean Language Dictionary API configuration from environment variables.
- Do not hard-code API keys, model names, or local machine-specific paths.
- Do not send the full judgment text to the LLM when a narrower lexical-unit context is sufficient.
- Do not treat LLM output as ground truth; preserve evidence, dictionary meanings, and confidence scores in intermediate JSON.
- Validate intermediate JSON before RDF generation.
- Do not produce RDF triples for metaphor judgments that failed validation or remain unresolved; preserve them in intermediate JSON with status and errors.
- Any dependency outside the approved dependency list requires explicit approval.
- All dependencies must be pinned in `pyproject.toml`.

## 4. Conventions

### Naming

- Project name: `ALL`
- Agent name: `ALL_Metaphor`
- File naming convention: Python files use `snake_case.py`.
- Function naming convention: Python functions use `snake_case`.
- Class naming convention: Python classes use `PascalCase`.
- RDF namespace naming convention: Use a minimal project namespace unless a stronger ontology requirement is later approved.
- RDF predicate naming convention: Use mapping-focused predicates that directly reflect MIPVU analysis outputs.

### Environment Variables

- `OPENAI_API_KEY`: OpenAI API key
- `OPENAI_MODEL`: OpenAI model name
- `KRDICT_API_KEY`: Standard Korean Language Dictionary API key
- `ALL_LOG_LEVEL`: Optional log level, defaults to `INFO`

### Skills

- Korean MIPVU adaptation rules live in `skills/korean-mipvu/SKILL.md`.
- Detailed MIPVU reference material lives in `skills/korean-mipvu/references/`.
- Use that skill when implementing or changing Korean lexical-unit metaphor identification logic.

### Code Layout

- `pyproject.toml`: pinned dependencies and tool configuration.
- `main.py`: compatibility wrapper for `python main.py ...`; delegate directly to `src/all_metaphor/cli.py:main()`.
- `src/all_metaphor/cli.py`: CLI entrypoint for `python -m all_metaphor.cli`. Use `argparse` only, require `--input`, `--json-output`, and `--ttl-output`, and delegate execution to `src/all_metaphor/pipeline.py:run_pipeline_to_files()`.
- `src/all_metaphor/config.py`: environment variables, runtime settings, and path defaults.
- `src/all_metaphor/pipeline.py`: orchestration of pipeline nodes.
- `src/all_metaphor/io.py`: `.txt` input loading.
- `src/all_metaphor/lexical_units.py`: word-level segmentation, character offsets, and local context windows.
- `src/all_metaphor/morphology.py`: KonLPy Okt wrapper, POS extraction, and dictionary-form normalization.
- `src/all_metaphor/candidate_filter.py`: particle, ending, punctuation, number, boilerplate, and low-signal token filtering.
- `src/all_metaphor/krdict_client.py`: Standard Korean Language Dictionary API client and per-run lookup cache.
- `src/all_metaphor/llm_client.py`: OpenAI API calls, structured prompts, response parsing, and token usage capture.
- `src/all_metaphor/schemas.py`: intermediate JSON data structures, enums, and schema version constants.
- `src/all_metaphor/validation.py`: intermediate JSON validation, LLM response validation, and RDF-readiness checks.
- `src/all_metaphor/rdf_mapper.py`: rdflib graph construction and Turtle serialization.
- `src/all_metaphor/output_writer.py`: UTF-8 intermediate JSON and Turtle file persistence.
- `src/all_metaphor/observability.py`: run IDs, logging, stage metrics, and token/dictionary/LLM counters.
- `src/all_metaphor/errors.py`: project-specific exceptions and error codes.
- `tests/`: pytest tests mirroring `src/all_metaphor/` modules.

### Processing Pipeline

1. `load_input`: Load and validate a `.txt` judgment document.
2. `segment_lexical_units`: Segment the text into word-level lexical units with character offsets and bounded local context.
3. `analyze_morphology`: Run KonLPy Okt morphological analysis, attach POS and lemma information, and normalize candidate content words to dictionary forms where possible.
4. `filter_candidates`: Exclude particles, endings, function words, punctuation, numbers, legal-structure stopwords, and clearly non-metaphorical tokens.
5. `lookup_dictionary_meanings`: Query the Standard Korean Language Dictionary API for candidate lexical-unit meanings.
6. `judge_metaphor`: Compare contextual meaning and dictionary meaning according to MIPVU, then ask the OpenAI API to judge metaphorical use for the filtered candidate set.
7. `validate_intermediate`: Validate schema, evidence, enum values, confidence ranges, and RDF readiness.
8. `write_intermediate_json`: Save validated intermediate analysis as JSON, or save partial JSON with validation errors.
9. `map_rdf`: Map only validated RDF-ready metaphor analysis results into RDF triples.
10. `write_turtle`: Save RDF output as Turtle (`.ttl`).

### Pipeline Nodes

- `load_input`: Load and validate a `.txt` judgment document.
- `segment_lexical_units`: Create word-level lexical units with character offsets and bounded local context.
- `analyze_morphology`: Run KonLPy Okt, attach POS/lemma information, and normalize candidate content words to dictionary forms where possible.
- `filter_candidates`: Remove particles, endings, function words, punctuation, numbers, legal-structure stopwords, and clearly non-metaphorical tokens before dictionary or LLM calls.
- `lookup_dictionary_meanings`: Fetch Standard Korean Language Dictionary meanings for candidate lexical units.
- `judge_metaphor`: Compare contextual and dictionary meanings according to MIPVU, then ask OpenAI to judge metaphorical use.
- `validate_intermediate`: Validate schema, required evidence, enum values, confidence ranges, and RDF readiness.
- `write_intermediate_json`: Save validated JSON output, or save partial JSON with validation errors.
- `map_rdf`: Convert only validated RDF-ready metaphor results to RDF triples.
- `write_turtle`: Serialize RDF as `.ttl`.

### Guardrails

- Keep MIPVU judgment evidence-based: every metaphor decision must retain the original surface form, local context, candidate dictionary meanings, and LLM rationale.
- Treat legal terms of art as non-metaphorical by default when their contextual meaning matches conventional legal usage.
- Prefer high precision over high recall in the first implementation; uncertain candidates should remain unresolved instead of being forced into RDF triples.
- Filter candidates before any LLM call using Okt POS tags, token length, punctuation, numeric checks, and legal-structure stopwords.
- Deduplicate candidate lemmas before dictionary lookup and LLM judgment.
- Cache dictionary lookup results per normalized lexical unit during a run.
- Keep OpenAI prompts structured and ask for machine-readable JSON only.
- Require metaphorical LLM judgments to include concise `source_domain` and `target_domain` labels; if either domain cannot be identified confidently, keep the candidate `unresolved`.
- Validate LLM responses against the intermediate JSON schema before RDF mapping.
- Preserve raw input text locally only; do not log full judgment text.
- Keep RDF output limited to validated entities and predicates from the project vocabulary unless a new predicate is explicitly approved.

### Pipeline Orchestration Rules

- `pipeline.py` only controls flow; analysis, validation, RDF mapping, and output writing stay delegated to their node modules.
- `run_pipeline(...)` runs through validation and RDF mapping but does not write files.
- `run_pipeline_to_files(...)` calls `run_pipeline(...)` first, then writes JSON and Turtle outputs without rerunning validation or RDF mapping.
- Pipeline logs may include stage names, document IDs, counts, and output paths, but not judgment text, local context, raw LLM prompts/responses, raw payloads, or API keys.
- LangGraph orchestration is TBD; M2-9 uses pure Python functions without adding a new dependency.

### CLI Rules

- `cli.py` only parses arguments, loads `RuntimeSettings`, calls `run_pipeline_to_files(...)`, and prints a safe summary.
- CLI execution must support `python -m all_metaphor.cli --input <txt> --json-output <json> --ttl-output <ttl>` and may also support the `all-metaphor` console script.
- CLI success exits with `0`; `AllMetaphorError` exits with `1`; unexpected exceptions exit with `2`; argparse validation uses argparse's default exit behavior.
- CLI stdout/stderr must not include judgment text, local context, raw LLM prompts/responses, raw payloads, tracebacks, or API keys.

### Glossary

- **MIPVU**: Metaphor Identification Procedure VU University Amsterdam.
- **MRW**: Metaphor-Related Word.
- **Lexical unit**: Word-level surface form before morphological decomposition.
- **Basic meaning**: Core, concrete, embodied dictionary sense of a word.
- **Contextual meaning**: Meaning of a word in its specific usage.
- **Indirect metaphor**: Contextual meaning differs from basic meaning and is understood by comparison.
- **Direct metaphor**: TBD.
- **Implicit metaphor**: TBD.
- **Lemma**: Dictionary form of a word.
- **POS**: Part of speech tag from KonLPy's Okt analyzer.

### Observability

Use lightweight local observability.

- Log one `run_id` per execution.
- Log pipeline stage start/end events.
- Track input file path, character count, lexical-unit count, candidate count, filtered candidate count, dictionary lookup count, LLM request count, and RDF triple count.
- Track OpenAI token usage when available from the API response.
- Track dictionary API failures, LLM validation failures, skipped candidates, and unresolved candidates.
- Store run metadata inside the intermediate JSON output.
- Console logs should be concise and must not include the full judgment text.

### Error Policy

- Missing input file: fail fast with a clear error message.
- Invalid file extension: fail fast unless explicitly overridden later.
- Empty input file: fail fast with a clear error message.
- UTF-8 text decoding failure: fail fast with a clear error message. Encoding fallback is TBD.
- Missing required environment variable: fail fast before processing begins.
- KonLPy Okt analysis failure for one lexical unit: record the error, skip that unit, and continue.
- Dictionary API failure for one candidate: retry with conservative backoff; if still failing, mark the candidate as `dictionary_error` and continue.
- OpenAI API failure: retry with conservative backoff; if still failing, save partial intermediate JSON and stop before RDF generation.
- Invalid LLM JSON: retry once with a repair prompt; if still invalid, mark affected candidates as `llm_validation_error`.
- Intermediate validation failure for one candidate: record `validation_error`, normalize the candidate to `unresolved` when RDF readiness cannot be guaranteed, and continue.
- RDF serialization failure: fail the run because the final output would be invalid.
- Output write failure: fail the run with `OUTPUT_WRITE_ERROR`; do not include payload, Turtle text, judgment text, local context, or secrets in the error message.
- Partial outputs must include a top-level `status` field such as `completed`, `partial`, or `failed`.

### Output Writer Rules

- `output_writer.py` only persists already-produced intermediate JSON and Turtle text; it does not validate, judge, or map RDF.
- Intermediate JSON must be written as UTF-8 with `ensure_ascii=False`, `indent=2`, and a trailing newline.
- Turtle text must be written as UTF-8 exactly as provided, except for ensuring a trailing newline.
- Parent output directories may be created automatically, but directory paths passed as output files must raise `OutputWriteError`.
- Output writer logs or errors must not include raw payloads, Turtle text, judgment text, local context, raw LLM responses, or API keys.

### Testing Policy

- Each `src/all_metaphor/*.py` module has a corresponding `tests/test_*.py`.
- Pipeline nodes are tested with mocked external dependencies, including OpenAI and the Standard Korean Language Dictionary API.
- Schema validators have positive and negative test cases.
- Integration test: run the pipeline on `data/input/sample.txt` and assert intermediate JSON validity.
- Target coverage: 70% for the first milestone.
- Use `pytest-cov` to measure the Testing Policy target coverage.

### Token Policy

- Send only filtered candidate lexical units to the LLM.
- Provide only a bounded local context window around each candidate, not the full judgment.
- Local context window per lexical unit: `±N` tokens, default `N=10`, maximum `N=30`.
- Local context must never include more than 100 characters per lexical unit.
- Include dictionary meanings from the Standard Korean Language Dictionary API instead of asking the LLM to invent basic meanings.
- Batch candidates only when doing so does not make the prompt too large or mix unrelated contexts.
- Deduplicate repeated lemmas and reuse previous dictionary results.
- Prefer compact JSON prompts and responses.
- Record prompt tokens, completion tokens, total tokens, and model name when available.
- Do not ask the LLM to judge particles, endings, punctuation, numbers, or obvious legal boilerplate tokens.

### Reproducibility

- Set the OpenAI `seed` parameter when available and log the seed.
- Set temperature explicitly; default is `0.0` for metaphor judgment and must be documented in code.
- Log model name, temperature, and seed in intermediate JSON.
- Same input, same model, and same seed should produce stable output.

### Intermediate JSON Schema

Intermediate JSON must be versioned and stable enough to support debugging and RDF generation.

```json
{
  "schema_version": "0.1",
  "project": "ALL",
  "agent": "ALL_Metaphor",
  "status": "completed | partial | failed",
  "run": {
    "run_id": "string",
    "started_at": "ISO-8601 string",
    "completed_at": "ISO-8601 string | null",
    "input_path": "string",
    "openai_model": "string",
    "openai_temperature": 0.0,
    "openai_seed": "integer | null",
    "context_window": {
      "tokens_before": 10,
      "tokens_after": 10,
      "max_tokens_each_side": 30,
      "max_characters": 100
    },
    "token_usage": {
      "prompt_tokens": 0,
      "completion_tokens": 0,
      "total_tokens": 0
    }
  },
  "document": {
    "document_id": "string",
    "source_file": "string",
    "character_count": 0
  },
  "lexical_units": [
    {
      "unit_id": "string",
      "surface": "string",
      "lemma": "string | null",
      "pos": "string | null",
      "start_char": 0,
      "end_char": 0,
      "sentence_id": "string | null",
      "local_context": "string",
      "local_context_char_count": 0,
      "is_candidate": true,
      "filter_reason": "string | null"
    }
  ],
  "candidates": [
    {
      "candidate_id": "string",
      "unit_id": "string",
      "dictionary_query": "string",
      "dictionary_meanings": [
        {
          "sense_id": "string | null",
          "definition": "string",
          "source": "standard_korean_language_dictionary"
        }
      ],
      "contextual_meaning": "string | null",
      "basic_meaning": "string | null",
      "meaning_contrast": "string | null",
      "mipvu_decision": "metaphorical | non_metaphorical | unresolved",
      "metaphor_type": "indirect | direct | implicit | null",
      "source_domain": "string | null",
      "target_domain": "string | null",
      "confidence": 0.0,
      "llm_rationale": "string | null",
      "errors": [
        {
          "error_code": "DICT_API_FAILURE | LLM_VALIDATION_ERROR | ...",
          "stage": "string",
          "candidate_id": "string | null",
          "message": "string",
          "retryable": true,
          "timestamp": "ISO-8601 string"
        }
      ]
    }
  ],
  "rdf": {
    "output_path": "string | null",
    "triple_count": 0,
    "confidence_threshold": 0.5
  },
  "errors": [
    {
      "error_code": "DICT_API_FAILURE | LLM_VALIDATION_ERROR | ...",
      "stage": "string",
      "candidate_id": "string | null",
      "message": "string",
      "retryable": true,
      "timestamp": "ISO-8601 string"
    }
  ]
}
```

`confidence` is the LLM-reported probability that the lexical unit is used metaphorically in this context. It must be in the range `[0.0, 1.0]`. Threshold for RDF inclusion is TBD; default is `0.5`.

### RDF Mapping Recommendation

Because the initial goal is mapping rather than modeling complex legal relationships, start with a minimal project-specific vocabulary.

- Project namespace: `ex: <http://example.org/legal-metaphor#>`
- Core resource types:
  - `ex:Document`
  - `ex:Sentence`
  - `ex:LexicalUnit`
  - `ex:MetaphorCandidate`
  - `ex:SourceDomain`
  - `ex:TargetDomain`
- Recommended predicates:
  - `ex:hasMIPVUDecision`
  - `ex:hasMetaphorType`
  - `ex:hasSourceDomain`
  - `ex:hasTargetDomain`
  - `ex:hasLexicalUnit`
  - `ex:hasSurfaceExpression`
  - `ex:hasContextualMeaning`
  - `ex:hasBasicMeaning`
  - `ex:hasMeaningContrast`
  - `ex:hasConfidence`
  - `ex:isMappedTo`
  - `ex:appearsInSentence`
  - `ex:appearsInDocument`
  - `ex:hasDictionaryMeaning`

Ontology alignment with RDF, RDFS, OWL, SKOS, or legal-domain ontologies is TBD.

### Folder Structure

Use the following minimal implementation structure once code is added.

```text
.
├── AGENTS.md
├── pyproject.toml
├── main.py
├── src/
│   └── all_metaphor/
├── tests/
├── skills/
│   └── korean-mipvu/
│       ├── SKILL.md
│       ├── references/
│       │   ├── mipvu_protocol.md
│       │   └── edge_cases.md
│       └── scripts/        # optional, only if needed
├── data/
│   └── input/
└── outputs/
    ├── intermediate/
    └── rdf/
```

Future folders are TBD and should be added only after their purpose is confirmed.

## 5. Commands

- Run: `python -m all_metaphor.cli --input data/input/example.txt --json-output outputs/intermediate/example.json --ttl-output outputs/rdf/example.ttl`
- Compatibility run: `python main.py --input data/input/example.txt --json-output outputs/intermediate/example.json --ttl-output outputs/rdf/example.ttl`
- Test: `pytest`
- Lint: `ruff check src/`
- Format: `ruff format src/`
- Type check: `mypy src/` (optional)
