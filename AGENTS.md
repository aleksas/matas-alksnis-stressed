# AGENTS.md

## Mission

This repository exists to produce the most complete stressed Lithuanian version possible of MATAS v1.0 and ALKSNIS v3.0, then publish that stressed dataset to Hugging Face.

## Working Priorities

- Maximize stressed-token coverage without silently lowering quality.
- Treat `datasets/*.zip` as immutable source artifacts.
- Prefer reproducible, morphology-aware stress sources before heuristic fallbacks.
- Keep ambiguity and unresolved cases visible.
- Preserve enough provenance to audit how each stressed form was produced.

## Repo-Specific Rules

- Use `python3`, not `python`.
- If host dependencies are missing, prefer the provided Docker environment before ad-hoc local setup.
- `stress_sentences.py` is the main generation path.
- `word_stress_db.py` is the reusable cache; extend or reuse it before recomputing everything.
- `corrections.py` and `tag_map.py` are the right place for corpus/tag cleanup rules.
- Do not overwrite or delete the original source ZIPs.
- When regenerating outputs, write them to extracted `*-stressed/` trees and only then package release ZIPs.

## Stress Resolution Strategy

Use this order unless there is a strong reason to do otherwise:

1. Existing stressed outputs or curated corrections.
2. `stress.sqlite.db` cache hits.
3. `vdu-nlp-services` with Jablonskis-tag-aware ranking.
4. Existing `lki.words` lookup fallback.
5. `phonology_engine` only after the earlier path still leaves the token unresolved or insufficiently reliable.
6. Explicit unresolved logging rather than silent guesswork.

## Provenance Expectations

Future changes should move toward recording the source of each stressed token. If you add or change fallback logic, prefer adding metadata that makes these categories recoverable later:

- cache
- `vdu-nlp-services`
- `lki.words`
- `phonology_engine`
- unresolved

## Next-Step Discipline

Until the repository goals are fully reached, every completed task should also identify the single best next step.

- Prefer the next step that most directly improves stressed-token coverage, ambiguity visibility, provenance, or HF publication readiness.
- Make the suggested next step concrete and measurable, not generic housekeeping.
- If progress is blocked, name the blocker and the next prerequisite step instead of pretending the mission is complete.
- A private or partial Hugging Face upload does not count as the publication goal being finished.

## Definition Of Done

A dataset-completion change is not done until it also:

- updates `README.md` if the workflow or publication target changes
- reports before/after coverage impact for ambiguous and unresolved tokens
- keeps the output format suitable for later HF export
- avoids destructive edits to upstream corpora or previously curated data without explicit justification
