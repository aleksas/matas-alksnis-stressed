# matas-alksnis-stressed

This repository is a working dataset-build project for producing stressed Lithuanian CoNLL-U corpora from two CLARIN resources:

- [Lithuanian Treebank - ALKSNIS v3.0](https://clarin.vdu.lt/xmlui/handle/20.500.11821/21)
- [Lithuanian morphologically annotated corpus - MATAS v1.0](https://clarin.vdu.lt/xmlui/handle/20.500.11821/33)

The current goal is to stress as much of both corpora as possible, keep unresolved and ambiguous cases visible, and publish a reproducible stressed dataset to Hugging Face.

## Direction

The repo already contains:

- original source archives in `datasets/*.zip`
- previously generated stressed archives in `datasets/*-stressed.zip`
- scripts for tag normalization, stress lookup, and sentence reconstruction

Work in this repository should now optimize for coverage and reproducibility:

- maximize stressed token coverage across MATAS and ALKSNIS
- prefer morphology-aware and deterministic stress sources first
- use `phonology_engine` as a fallback when the conventional path cannot resolve stress reliably
- keep provenance and ambiguity visible so later review is possible
- prepare the final artifact for Hugging Face publication

## Short-Term Target: Technical Paper

Prepare a concise technical paper that makes the dataset-building decisions reproducible and reviewable. The paper should document:

- the source corpora and every cleanup or selection choice
- every tool used, including versions and the reason each tool was chosen
- the reconstructed 2020 generation path through the VDU Kirtis SOAP service (accessed through the `vdu-nlp-services` Python client), tag conversion, morphology-aware variant ranking, the word-list fallback, and the provenance that the old archives did not retain
- the complete stress-resolution order and ambiguity-ranking rules
- the history of `phonology_engine` as Aleksas Pielikis's earlier derivative work on LIEPA-1, its separate licence and upstream attribution, and its reuse for corpus annotation outside LIEPA-1's intended speech-synthesis setting
- a detailed explanation of the LIEPA/`phonology_engine` sentence-processing fallback, including normalization, word-to-token mapping, acceptance checks, and failure handling
- before-and-after coverage, ambiguity, and unresolved-token measurements for both corpora
- token provenance, known limitations, rejected alternatives, and the exact steps needed to rebuild the published dataset

The immediate deliverable is a reviewable `TECHNICAL_PAPER.md` draft with enough detail for another researcher to reproduce the pipeline and audit its choices.

## Reference Tools

- VDU Kirtis: the automatic accentuation service used for the 2020 build (accessed through [`vdu-nlp-services`](https://github.com/aleksas/vdu-nlp-services))
- [`phonology_engine`](https://github.com/aleksas/phonology_engine): fallback engine for unresolved or weakly resolved cases
- VDU, [*Lietuvių kalbos teksto kirčiavimas internete* final report](https://sitti.vdu.lt/wp-content/uploads/2025/02/T_41_05_ataskaita.pdf): original resources, rules, and evaluation
- Asta Kazlauskienė, Gailius Raškinis, Airenas Vaičiūnas, [*Automatinis lietuvių kalbos žodžių skiemenavimas, kirčiavimas, transkribavimas*](https://portalcris.vdu.lt/server/api/core/bitstreams/5e0a886f-e75c-4716-b7e7-a3c0ed837b9f/content): full algorithm and resource description

## Bundled Corpora

- `datasets/Alksnis-3.0.zip`: source ALKSNIS archive, `76` CoNLL-U files
- `datasets/MATAS-v1.0.zip`: source MATAS archive, `138` CoNLL-U files
- `datasets/Alksnis-3.0-stressed.zip`: existing stressed ALKSNIS release, `76` CoNLL-U files
- `datasets/MATAS-v1.0-stressed.zip`: existing stressed MATAS release, `138` CoNLL-U files

According to the upstream MATAS readme bundled in this repo, MATAS v1.0 contains `1,693,410` wordforms and `144,047` sentences.

## How the Published Hugging Face Corpus Was Built

The current [`meldynamics/lt-stressed-corpus`](https://huggingface.co/datasets/meldynamics/lt-stressed-corpus) is not the result of running one current service over the source Parquet. It has a two-stage lineage: a 2020 conversion from the original CoNLL-U corpora into stressed CoNLL-U archives, followed by a later rebuild that preserved those stress forms, filled part of the unresolved tail, and exported a filtered sentence dataset.

### Source annotation

MATAS and ALKSNIS supplied the linguistic annotation used for stress selection:

- token and sentence boundaries;
- surface form and lemma;
- Jablonskis/XPOS analysis;
- UD part of speech and morphological features;
- dependency heads and relations in ALKSNIS.

MATAS is described upstream as manually checked morphological annotation. Neither source corpus supplied the stress layer added here. The build did not send the sentences to a service to replace their morphology: it retained the source annotation and canonicalized a small set of Jablonskis spellings, such as `dktv.` to `dkt.`, so that corpus and service tags could be compared.

### 2020 VDU selection

For every token considered stressable, the 2020 code:

1. read the token's surface form, lemma, and canonicalized Jablonskis tag set;
2. checked the local form/tag cache and, on a miss, queried the old VDU Kirtis SOAP service for the isolated surface word (using the `vdu-nlp-services` Python client);
3. converted the returned stress notation to Unicode and the returned grammatical labels to Jablonskis tags;
4. ranked the returned analyses by matching part-of-speech category, then by the number of tags shared with the corpus annotation, then by fewer unmatched/extra service tags;
5. selected the first result after that deterministic sort, recovered the source capitalization, and wrote it as token-level `StressedForm`;
6. recorded sentence counters for unique, multiple, missing, and equally best stress options.

The client targeted `http://donelaitis.vdu.lt/Kirtis/KServisas.php?wsdl`, called its `kirciuok` operation, and requested Kirtis engine version `8.0`. VDU reports that the current web Kirčiuoklis replaced the original interface in 2021; the current service did not produce the published corpus.

This was morphology-conditioned word lookup, not contextual sentence disambiguation. The call contained one word, and the selection code did not use surrounding tokens or dependency relations. The source lemma was carried into the cache path, but the option-ranking function compared the surface form and tag sets rather than lemma identity.

The builder did not call VDU's separate text-morphology endpoint. Its comparison morphology came from the MATAS/ALKSNIS CoNLL-U annotations. Lemuoklis mattered as an internal component of the VDU Kirtis system described below, not as a second annotation request made by this repository.

VDU's own documentation describes what stood behind the returned candidates. The accentuator used Lemuoklis morphology, a syllabifier, formalized accentuation rules, and lexical resources for nouns/adjectives, numerals, pronouns, verbs, invariant words, personal names, and place names. The documented sources include the *Dabartinės lietuvių kalbos žodynas*, standard-Lithuanian accentuation references, a suffixal-verb accentuation reference, and VLKK recommendations. Those VDU dictionaries were not copied into this repository; the 2020 build stored selected outputs from the service.

When the VDU path did not produce a stressed form, the code tried an exact lowercase lookup in a separate stressed-word collection assembled from LKIIS exports. Its four inputs were the modern Lithuanian dictionary, historical place names, surnames, and the Lithuanian–Latvian dictionary. This fallback did not compare morphology; it removed stress for the lookup key and then restored the corpus token's capitalization.

The 2020 output archives retained `StressedForm` and ambiguity counters but no token-level source label. A form from those archives could therefore have come from the VDU response/cache path or the LKIIS lookup. This is why the current export calls all such carried forms `legacy` instead of claiming exact provider provenance.

### Current rebuild and export

The published Hugging Face artifact was rebuilt from the stressed archives with `--input-stressed`; it did not re-query the current VDU Kirčiuoklis for every token. The rebuild:

1. preserved every existing valid `StressedForm` and labelled it `legacy`;
2. retried unresolved tokens against the local cache and LKIIS-derived exact-form lookup;
3. passed eligible, number-free sentences through `phonology_engine` as the final fallback;
4. accepted a `phonology_engine` result only when its source span mapped to the same token and removing the stress marks reproduced the original form;
5. reconstructed the Unicode-stressed sentence using the CoNLL-U token order and spacing metadata;
6. exported only sentences with no unresolved stressable token and no Arabic- or Roman-numeral token. A Roman numeral must be upper case and tagged `sktv.`: the numeral `dvi` (two) is spelled with Roman-numeral letters, and a case-insensitive match had excluded every sentence containing it.

The published `111,719` sentences contain `1,152,480` stressable word occurrences. Their visible current-rebuild provenance is:

| Current `stress_source` | Words | Exact meaning |
| --- | ---: | --- |
| `legacy` | 1,143,782 | Carried from the 2020 stressed archives; usually VDU-based, but the old archives cannot separate their internal cache/LKIIS fallbacks |
| `lki.words` | 1,684 | Newly filled by exact destressed-form lookup in the LKIIS-derived collection |
| `phonology_engine` | 7,014 | Newly filled by accepted sentence-level LIEPA-style output |
| `cache` or fresh VDU call | 0 | No published token was newly attributed to either path during this archive rebuild |

The source pool contained `147,670` sentences. The public export omitted `35,951` because they still contained an unresolved stressable word, an Arabic/Roman numeral, or both. “Fully stressed” therefore describes the selected subset; it does not mean every selected stress was unambiguous or manually verified.

### Provenance limitations

The repository can reproduce the current Hugging Face files from the checked-in stressed archives, but it cannot independently replay every 2020 decision: the raw SOAP responses and a frozen VDU engine are absent, while `legacy` conflates the VDU response/cache path with the original LKIIS fallback. The stressed layer is predominantly automatic and has not been exhaustively human-verified. The LKIIS fallback also retained no per-form resource identifier. Finally, MATAS/ALKSNIS licensing and external stress-source redistribution are distinct questions; the latter should be reviewed before a new release is regenerated directly from VDU or LKIIS systems.

## Current Pipeline

- `archive_iterator.py` streams CoNLL-U files directly from the ZIP archives.
- `stress_sentences.py` normalizes Jablonskis tags, queries VDU Kirtis when live lookup is enabled (through `vdu-nlp-services`), reuses the SQLite cache, applies `lki.words`, and then uses sentence-level `phonology_engine` fallback for still-unresolved tokens before writing stressed CoNLL-U files.
- `word_stress_db.py` stores `(form, lemma, tag-set) -> stressed form` mappings in `stress.sqlite.db`.
- `sentences.py` reconstructs plain or stressed sentences from the dataset archives.
- `sentence_backlog.py` exports a sentence backlog sorted by unresolved load and completion so the incomplete tail can be targeted first.
- `corrections.py` and `tag_map.py` hold corpus-specific normalization rules and should be extended before adding ad-hoc logic elsewhere.

The stressed outputs store token-level `StressedForm` and `StressSource` values and sentence-level metadata such as:

- `stressed_sentence`
- `single_stress_option_word_count`
- `multiple_stress_option_word_count`
- `no_stress_option_word_count`
- `multiple_best_stress_option_word_count`
- `legacy_word_count`
- `cache_word_count`
- `vdu_nlp_services_word_count`
- `lki_words_word_count`
- `phonology_engine_word_count`
- `unresolved_word_count`

## Current Baseline

The checked-in stressed archives already expose the remaining problem areas through sentence metadata:

| Corpus | Sentences | Single option | Multiple options | No stress option | No stress option with tags | Multiple best options |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ALKSNIS v3.0 | 3,642 | 45,306 | 8,406 | 906 | 815 | 502 |
| MATAS v1.0 | 144,028 | 1,338,122 | 242,138 | 30,606 | 25,287 | 14,672 |

Those counts show that the dataset is already far along, but there are still tens of thousands of unresolved or ambiguous MATAS tokens and a smaller unresolved tail in ALKSNIS. That is the main remaining gap before an HF release is credible.

## Preferred Stress Resolution Order

This is the intended order for future dataset-completion work:

1. Reuse already stressed outputs and any manually curated fixes.
2. Reuse cached results from `stress.sqlite.db`.
3. Query VDU Kirtis with Jablonskis tag matching and ranking (through `vdu-nlp-services.stress_word`).
4. Use the existing `lki.words` fallback for direct stressed-word lookups.
5. Try `phonology_engine` when the earlier steps still leave the token unresolved or weakly resolved.
6. Keep unresolved tokens auditable instead of fabricating a stress mark.

When adding new fallback behavior, prefer storing provenance so a later HF export can distinguish between:

- deterministic morphology-aware matches
- cache hits
- dictionary fallbacks
- `phonology_engine` fallbacks
- unresolved tokens

## Setup

Use Python 3. The current environment for this repo does not expose a `python` binary, so use `python3` explicitly.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Docker

The repo now includes a containerized development environment:

```bash
docker compose build
docker compose run --rm app bash
```

From there you can run the pipeline inside the container:

```bash
python3 stress_sentences.py
```

The compose setup mounts the current workspace into `/workspace`, so source archives and generated outputs stay on the host filesystem.

## Hugging Face Export

The repository now includes an HF export helper that turns the current stressed archives into a sentence-level dataset with two schema profiles:

```bash
docker compose run --rm app python3 hf_dataset.py export
```

That default export writes both HF configs into `hf_export_lt_stressed_corpus/`:

- `data/default/train.parquet` slim public schema
- `data/full/train.parquet` full provenance schema
- `README.md` dataset card
- `COLUMNS.md` field-by-field schema reference
- `summary.json`

If you only want one schema profile locally:

```bash
docker compose run --rm app python3 hf_dataset.py export --profile default
docker compose run --rm app python3 hf_dataset.py export --profile full
```

By default, the HF export now keeps only:

- fully stressed sentences
- sentences without Arabic-digit or Roman-numeral tokens

The full row schema is still preserved for every exported sentence.

If you need the previous all-sentences export for internal analysis, opt back in explicitly:

```bash
docker compose run --rm app python3 hf_dataset.py export --include-unresolved --include-number-sentences
```

The export now preserves substantially more of the original CoNLL-U structure and stressed metadata, including:

- serialized CoNLL-U sentence blocks
- the full sentence-level metadata map
- token-level annotations, tags, features, dependency fields, and misc maps
- token-level stressed forms and stress-source provenance

The dataset card keeps the main columns concise and links to `COLUMNS.md` for the full schema.
Both configs keep the full `tokens` records and intentionally omit duplicate flat `token_*` mirrors and other convenience-only fields that can be reconstructed from the remaining data.

Columns shared by both configs:

- `source_dataset`
- `source_file`
- `sent_id`
- `newdoc_id`
- `newpar_id`
- `original_text`
- `original_text_raw`
- `stressed_text_unicode`
- `tokens`

Additional shared columns:

- `sktv_token_count`, `digit_token_count`, `roman_numeral_token_count`
- `single_stress_option_word_count`
- `multiple_stress_option_word_count`
- `no_stress_option_word_count`
- `no_stress_option_with_tags_word_count`
- `multiple_best_stress_option_word_count`
- `legacy_word_count`, `cache_word_count`, `vdu_nlp_services_word_count`, `lki_words_word_count`, `phonology_engine_word_count`, `unresolved_word_count`
- `words_with_multiple_best_stress_options`

Dependency edges in `tokens[*].deps` are exported as typed objects with `deprel`, `head`, and `raw` fields so the HF viewer can parse them reliably.

Fields only in `full`:

- `conllu_sentence`
- `sentence_metadata`

If you want to upload the prepared folder, set `HF_TOKEN` in `.env` and either pass `--repo-id` or set `HF_DATASET_REPO_ID`:

```bash
docker compose run --rm app python3 hf_dataset.py publish --repo-id your-username/lt-stressed-corpus
```

The same export filters apply during `publish`; use `--profile default`, `--profile full`, or the default `all` behavior together with `--include-unresolved` and `--include-number-sentences` only if you intentionally want a broader dataset.

## Sentence Backlog Export

To export the sentence queue sorted by completion and unresolved load:

```bash
docker compose run --rm app python3 sentence_backlog.py export
```

That command writes `sentence_backlog_lt_stressed/backlog.jsonl` and `sentence_backlog_lt_stressed/summary.json`.

If you only want the incomplete queue that still needs work:

```bash
docker compose run --rm app python3 sentence_backlog.py export --incomplete-only
```

The backlog rows include:

- source identifiers such as `source_dataset`, `source_file`, `sent_id`
- sentence text in `original_text` and `stressed_text`
- completion fields such as `resolved_word_count`, `evaluable_word_count`, and `completion_ratio`
- ambiguity and unresolved counts for prioritizing follow-up work

## Generating Stressed Files

```bash
python3 stress_sentences.py
```

The generator now applies the existing resolution order first, then runs a sentence-level `phonology_engine` pass only for words that are still unresolved and only in sentences without Arabic or Roman numeral tokens that would require normalization.

If the historical VDU Kirtis SOAP endpoint is unavailable, regenerate from the checked-in stressed archives instead:

```bash
python3 stress_sentences.py --input-stressed --overwrite
```

That mode preserves already stressed tokens as `StressSource=legacy`, then retries only the unresolved tail using the local cache, `lki.words`, and sentence-level `phonology_engine`.

The current generator writes extracted stressed CoNLL-U trees to:

- `Alksnis-3.0-stressed/`
- `MATAS-v1.0-stressed/`

If you regenerate data for release comparison or publication, package those trees back into `datasets/Alksnis-3.0-stressed.zip` and `datasets/MATAS-v1.0-stressed.zip`.

## Gaps Before Hugging Face Publication

- measure and review the before/after impact of the new `phonology_engine` fallback on unresolved and ambiguous counts
- surface token-level provenance in the HF export so downstream consumers can audit the chosen stress source
- replace or refresh the stale tests so they validate the current pipeline
- add a reproducible export step for HF-friendly artifacts such as JSONL, Parquet, or `datasets`
- prepare a dataset card with source licenses, coverage stats, and unresolved-case policy
