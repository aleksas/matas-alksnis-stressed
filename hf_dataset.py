import argparse
import json
import os
import re
import shutil
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from conllu import parse_incr
from archive_iterator import get_dataset_connlu_files


DIGIT_PATTERN = re.compile(r"\d")
# Upper case only: the numeral `dvi` (two) is spelled with Roman-numeral letters
# and is tagged `sktv.`, so a case-insensitive match dropped every sentence with it.
ROMAN_NUMERAL_PATTERN = re.compile(r"^[IVXLCDM]+$")

DATASET_TITLE = "LT Stressed Corpus"
DATASET_SLUG = "lt-stressed-corpus"

DEFAULT_OUTPUT_DIR = Path("hf_export_lt_stressed_corpus")
DEFAULT_FULLY_STRESSED_ONLY = True
DEFAULT_EXCLUDE_NUMBER_SENTENCES = True
DEFAULT_EXPORT_PROFILE = "all"

BASE_EXPORT_FIELDS = [
    "source_dataset",
    "source_file",
    "sent_id",
    "newdoc_id",
    "newpar_id",
    "original_text",
    "original_text_raw",
    "stressed_text_unicode",
    "conllu_sentence",
    "sentence_metadata",
    "sktv_token_count",
    "digit_token_count",
    "roman_numeral_token_count",
    "tokens",
    "single_stress_option_word_count",
    "multiple_stress_option_word_count",
    "no_stress_option_word_count",
    "no_stress_option_with_tags_word_count",
    "multiple_best_stress_option_word_count",
    "legacy_word_count",
    "cache_word_count",
    "vdu_nlp_services_word_count",
    "lki_words_word_count",
    "phonology_engine_word_count",
    "unresolved_word_count",
    "words_with_multiple_best_stress_options",
]

EXPORT_PROFILE_SPECS = {
    "default": {
        "hf_config_name": "default",
        "title": "Slim public schema",
        "description": "Keeps the sentence text, token records, and stress/provenance counts.",
        "drop_fields": {"conllu_sentence", "sentence_metadata"},
        "staging_jsonl_path": Path("_staging/default/train.jsonl"),
        "parquet_path": Path("data/default/train.parquet"),
    },
    "full": {
        "hf_config_name": "full",
        "title": "Full provenance schema",
        "description": "Adds serialized CoNLL-U and full sentence metadata on top of the slim schema.",
        "drop_fields": set(),
        "staging_jsonl_path": Path("_staging/full/train.jsonl"),
        "parquet_path": Path("data/full/train.parquet"),
    },
}

EXPORT_PROFILE_ALIASES = {
    "public": "default",
}

SOURCE_DATASET_INFO = {
    "alksnis": {
        "title": "Lithuanian Treebank - ALKSNIS v3.0",
        "url": "https://clarin-repo.lt/items/a9db057d-de4e-45ee-9645-45f408592d76",
        "description": "Lithuanian dependency treebank distributed here in CoNLL-U.",
        "license_name": "Creative Commons Attribution 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "citation": "Bielinskienė A., Boizou L., Kovalevskaitė J., Rimkutė E. 2016: Lithuanian Dependency Treebank ALKSNIS. Proceedings of the Seventh International Conference Baltic HLT 2016. Amsterdam: IOS Press, 107–114.",
        "notes": [
            "The bundled readme says v3.0 includes a full syntactic review, uses the Jablonskis tagset, and adds administrative texts, scientific abstracts, and reviews.",
        ],
    },
    "matas": {
        "title": "MATAS v1.0",
        "url": "https://clarin-repo.lt/items/446d56d4-2695-481b-9b67-c4e1f91b6067",
        "description": "Manually checked, morphologically annotated Lithuanian corpus distributed here in CoNLL-U.",
        "license_name": "Creative Commons Attribution 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "citation": "Rimkutė E., Daudaravičius V., Utka A. 2007: Morphological Annotation of the Lithuanian Corpus. Proceedings of the 45th Annual Meeting of the Association for Computational Linguistics; Workshop Balto-Slavonic Natural Language Processing 2007, Prague, 94–99.",
        "notes": [
            "The bundled readme reports 1,693,410 wordforms and 144,047 sentences in the original release.",
            "The bundled readme lists five broad genres: documents, fiction, scientific texts, news, and transcripts.",
        ],
    },
}

STRESS_SOURCE_INFO = {
    "legacy": {
        "word_count_key": "legacy_word_count",
        "sentence_count_key": "legacy_sentence_count",
        "label": "forms carried forward from the 2020 VDU-based build",
        "description": "Stress carried over from the 2020 stressed MATAS/ALKSNIS archives. Repository history indicates that these forms were produced mainly from VDU Kirtis service variants selected with morphology-aware ranking; the old archives did not retain a token-level source field.",
    },
    "cache": {
        "word_count_key": "cache_word_count",
        "sentence_count_key": "cache_sentence_count",
        "label": "SQLite cache",
        "description": "Matches from the local `stress.sqlite.db` cache keyed by form, lemma, and tag set.",
    },
    "vdu-nlp-services": {
        "word_count_key": "vdu_nlp_services_word_count",
        "sentence_count_key": "vdu_nlp_services_sentence_count",
        "label": "VDU morphology-aware service",
        "description": "Morphology-aware stress lookup and Jablonskis-tag ranking against VDU Kirtis (accessed through `vdu-nlp-services`).",
    },
    "lki.words": {
        "word_count_key": "lki_words_word_count",
        "sentence_count_key": "lki_words_sentence_count",
        "label": "direct stressed-word lookup",
        "description": "Fallback dictionary lookup using the `lki.words` stressed form list.",
    },
    "phonology_engine": {
        "word_count_key": "phonology_engine_word_count",
        "sentence_count_key": "phonology_engine_sentence_count",
        "label": "speech-synthesis fallback",
        "description": "Sentence-level fallback implemented with `phonology_engine`, Aleksas Pielikis's earlier derivative work on the text-normalization and stress components of the LIEPA-1 synthesizer.",
    },
    "unresolved": {
        "word_count_key": "unresolved_word_count",
        "sentence_count_key": "unresolved_sentence_count",
        "label": "unresolved",
        "description": "Stressable words that still had no accepted stress form after the available fallbacks.",
    },
}


def load_env_file(path=".env"):
    env = {}
    env_path = Path(path)
    if not env_path.exists():
        return env

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip()

    return env


def get_env_value(key, default=None):
    return os.environ.get(key) or load_env_file().get(key, default)


def format_int(value):
    return f"{int(value):,}"


def format_pct(part, whole):
    if not whole:
        return "0.00%"
    return f"{(part / whole) * 100:.2f}%"


def normalize_sentence_text(text):
    if not text:
        return ""
    return text.rstrip()


def json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def deps_to_export(deps):
    if not deps:
        return []

    exported = []
    for dep in deps:
        if isinstance(dep, (list, tuple)) and len(dep) >= 2:
            exported.append({
                "deprel": dep[0],
                "head": dep[1],
                "raw": None,
            })
        else:
            exported.append({
                "deprel": None,
                "head": None,
                "raw": json.dumps(json_safe(dep), ensure_ascii=False),
            })

    return exported


def reconstruct_sentence(tokenlist, stressed=False):
    parts = []
    for token in tokenlist:
        token_id = token["id"]
        if not isinstance(token_id, int):
            continue

        form = token["form"]
        if form == "<g/>":
            continue

        if stressed:
            form = (
                token.get("misc", {}).get("StressedForm")
                if token.get("misc")
                else None
            ) or form

        parts.append(form)

        no_space_after = False
        try:
            no_space_after = token["misc"]["SpaceAfter"] == "No"
        except (TypeError, KeyError):
            no_space_after = False

        if not no_space_after:
            parts.append(" ")

    return normalize_sentence_text("".join(parts))


def parse_int_metadata(metadata, key):
    value = metadata.get(key)
    return int(value) if value else 0


def parse_list_metadata(metadata, key):
    value = metadata.get(key, "")
    if not value:
        return []
    return [item for item in value.split(",") if item]


def get_token_xpos(token):
    return token.get("xpos") or token.get("xpostag")


def get_token_upos(token):
    return token.get("upos") or token.get("upostag")


def is_word_token(token):
    return isinstance(token["id"], int)


def is_gap_token(token):
    return token.get("form") == "<g/>"


def get_word_tokens(tokenlist):
    return [
        token
        for token in tokenlist
        if is_word_token(token) and not is_gap_token(token)
    ]


def get_token_misc_value(token, key):
    misc = token.get("misc")
    if not misc:
        return None
    return misc.get(key)


def get_token_stressed_form(token):
    return get_token_misc_value(token, "StressedForm") or token.get("form")


def get_token_stress_source(token):
    return get_token_misc_value(token, "StressSource")


def is_roman_numeral_token(token):
    form = token.get("form") or ""
    xpos = get_token_xpos(token)
    return bool((xpos or "").startswith("sktv.") and ROMAN_NUMERAL_PATTERN.fullmatch(form))


def get_export_token_stress_source(token):
    source = get_token_stress_source(token)
    if source:
        return source

    form = token.get("form") or ""
    upos = get_token_upos(token) or ""
    xpos = get_token_xpos(token) or ""
    feats = token.get("feats") or {}

    if (
        upos == "PUNCT"
        or upos == "X"
        or upos == "SYM"
        or xpos.startswith("skyr.")
        or xpos in {"užs.", "akr.", "sutr."}
        or feats.get("Foreign") == "Yes"
        or feats.get("Abbr") == "Yes"
        or is_roman_numeral_token(token)
        or DIGIT_PATTERN.search(form)
        or not any(char.isalpha() for char in form)
    ):
        return "not_applicable"

    return "unresolved"


def get_export_token_head(token):
    head = token.get("head")
    return head if isinstance(head, int) else -1


def token_to_export_dict(token):
    token_id = token.get("id")

    if isinstance(token_id, tuple):
        if len(token_id) >= 2 and token_id[1] == "-":
            token_id_type = "multiword"
        elif len(token_id) >= 2 and token_id[1] == ".":
            token_id_type = "empty_node"
        else:
            token_id_type = "tuple"
    elif isinstance(token_id, int):
        token_id_type = "word"
    else:
        token_id_type = type(token_id).__name__

    form = token.get("form") or ""
    return {
        "id": json_safe(token_id),
        "id_raw": str(token_id),
        "id_type": token_id_type,
        "form": form,
        "lemma": token.get("lemma"),
        "upos": get_token_upos(token),
        "xpos": get_token_xpos(token),
        "feats": json_safe(token.get("feats")),
        "head": get_export_token_head(token),
        "deprel": token.get("deprel"),
        "deps": deps_to_export(token.get("deps")),
        "misc": json_safe(token.get("misc")),
        "stressed_form": get_token_stressed_form(token),
        "stress_source": get_export_token_stress_source(token),
        "contains_digit": bool(DIGIT_PATTERN.search(form)),
        "is_roman_numeral": is_roman_numeral_token(token),
        "is_gap_token": is_gap_token(token),
        "is_word_token": is_word_token(token),
    }


def get_source_dataset_name(source_file):
    if source_file.startswith("MATAS-v1.0-stressed/"):
        return "matas"
    if source_file.startswith("Alksnis-3.0-stressed/"):
        return "alksnis"
    raise ValueError("Unknown stressed source path: %s" % source_file)


def update_context(context, metadata):
    if metadata.get("newdoc id"):
        context["newdoc_id"] = metadata.get("newdoc id")
    if metadata.get("newpar id"):
        context["newpar_id"] = metadata.get("newpar id")


def normalize_profile_name(profile):
    normalized = EXPORT_PROFILE_ALIASES.get(profile, profile)
    if normalized == "all":
        return normalized
    if normalized not in EXPORT_PROFILE_SPECS:
        raise SystemExit("Unknown export profile: %s" % profile)
    return normalized


def resolve_profile_names(profile):
    normalized = normalize_profile_name(profile)
    if normalized == "all":
        return list(EXPORT_PROFILE_SPECS.keys())
    return [normalized]


def get_profile_field_order(profile_name):
    drop_fields = EXPORT_PROFILE_SPECS[profile_name]["drop_fields"]
    return [field for field in BASE_EXPORT_FIELDS if field not in drop_fields]


def row_for_profile(row, profile_name):
    profile_row = dict(row)
    for field in EXPORT_PROFILE_SPECS[profile_name]["drop_fields"]:
        profile_row.pop(field, None)
    return profile_row


def sentence_row(tokenlist, source_file, context):
    metadata = tokenlist.metadata
    source_dataset = get_source_dataset_name(source_file)
    word_tokens = get_word_tokens(tokenlist)
    exported_tokens = [token_to_export_dict(token) for token in tokenlist]
    original_text = normalize_sentence_text(
        metadata.get("sentence_rebuilt") or reconstruct_sentence(tokenlist, stressed=False)
    )
    original_text_raw = normalize_sentence_text(metadata.get("text") or original_text)
    stressed_text_unicode = normalize_sentence_text(
        metadata.get("stressed_sentence") or reconstruct_sentence(tokenlist, stressed=True)
    )

    multiple_stress_option_word_count = parse_int_metadata(metadata, "multiple_stress_option_word_count")
    no_stress_option_word_count = parse_int_metadata(metadata, "no_stress_option_word_count")
    no_stress_option_with_tags_word_count = parse_int_metadata(metadata, "no_stress_option_with_tags_word_count")
    multiple_best_stress_option_word_count = parse_int_metadata(metadata, "multiple_best_stress_option_word_count")
    legacy_word_count = parse_int_metadata(metadata, "legacy_word_count")
    cache_word_count = parse_int_metadata(metadata, "cache_word_count")
    vdu_nlp_services_word_count = parse_int_metadata(metadata, "vdu_nlp_services_word_count")
    lki_words_word_count = parse_int_metadata(metadata, "lki_words_word_count")
    phonology_engine_word_count = parse_int_metadata(metadata, "phonology_engine_word_count")
    unresolved_word_count = parse_int_metadata(metadata, "unresolved_word_count")

    sktv_token_count = sum(
        1 for token in word_tokens
        if (get_token_xpos(token) or "").startswith("sktv.")
    )
    digit_token_count = sum(
        1 for token in word_tokens
        if DIGIT_PATTERN.search(token["form"])
    )
    roman_numeral_token_count = sum(
        1 for token in word_tokens
        if is_roman_numeral_token(token)
    )

    return {
        "source_dataset": source_dataset,
        "source_file": source_file,
        "sent_id": metadata["sent_id"],
        "newdoc_id": context.get("newdoc_id"),
        "newpar_id": context.get("newpar_id") or "",
        "original_text": original_text,
        "original_text_raw": original_text_raw,
        "stressed_text_unicode": stressed_text_unicode,
        "conllu_sentence": tokenlist.serialize(),
        "sentence_metadata": json_safe(dict(metadata)),
        "sktv_token_count": sktv_token_count,
        "digit_token_count": digit_token_count,
        "roman_numeral_token_count": roman_numeral_token_count,
        "tokens": exported_tokens,
        "single_stress_option_word_count": parse_int_metadata(metadata, "single_stress_option_word_count"),
        "multiple_stress_option_word_count": multiple_stress_option_word_count,
        "no_stress_option_word_count": no_stress_option_word_count,
        "no_stress_option_with_tags_word_count": no_stress_option_with_tags_word_count,
        "multiple_best_stress_option_word_count": multiple_best_stress_option_word_count,
        "legacy_word_count": legacy_word_count,
        "cache_word_count": cache_word_count,
        "vdu_nlp_services_word_count": vdu_nlp_services_word_count,
        "lki_words_word_count": lki_words_word_count,
        "phonology_engine_word_count": phonology_engine_word_count,
        "unresolved_word_count": unresolved_word_count,
        "words_with_multiple_best_stress_options": parse_list_metadata(metadata, "words_with_multiple_best_stress_options"),
    }


def row_has_number_token(row):
    return row["digit_token_count"] > 0 or row["roman_numeral_token_count"] > 0


def row_has_unresolved_stress(row):
    return row["no_stress_option_word_count"] > 0


def row_has_ambiguous_stress(row):
    return (
        row["multiple_stress_option_word_count"] > 0
        or row["multiple_best_stress_option_word_count"] > 0
    )


def row_word_token_count(row):
    return sum(1 for token in row["tokens"] if token["is_word_token"])


def should_export_row(row, fully_stressed_only=True, exclude_number_sentences=True):
    if fully_stressed_only and row_has_unresolved_stress(row):
        return False
    if exclude_number_sentences and row_has_number_token(row):
        return False
    return True


def write_parquet_export(jsonl_path, parquet_path):
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "The HF export now writes Parquet. Install the `datasets` and `pyarrow` packages first."
        ) from exc

    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    if parquet_path.exists():
        parquet_path.unlink()

    dataset = load_dataset("json", data_files=str(jsonl_path), split="train")
    dataset.to_parquet(str(parquet_path))


def export_dataset(
    output_dir,
    fully_stressed_only=DEFAULT_FULLY_STRESSED_ONLY,
    exclude_number_sentences=DEFAULT_EXCLUDE_NUMBER_SENTENCES,
    profile=DEFAULT_EXPORT_PROFILE,
):
    output_dir = Path(output_dir)
    selected_profiles = resolve_profile_names(profile)

    shutil.rmtree(output_dir / "_staging", ignore_errors=True)
    shutil.rmtree(output_dir / "data", ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "selected_profiles": selected_profiles,
        "row_count": 0,
        "input_row_count": 0,
        "filters": {
            "fully_stressed_only": fully_stressed_only,
            "exclude_number_sentences": exclude_number_sentences,
        },
        "by_source_dataset": {},
        "input_by_source_dataset": {},
        "profiles": {},
    }
    source_dataset_counters = {}
    input_source_dataset_counters = {}

    profile_paths = {}
    profile_columns = {
        profile_name: get_profile_field_order(profile_name)
        for profile_name in selected_profiles
    }

    with ExitStack() as stack:
        profile_outputs = {}
        for profile_name in selected_profiles:
            spec = EXPORT_PROFILE_SPECS[profile_name]
            staging_jsonl_path = output_dir / spec["staging_jsonl_path"]
            parquet_path = output_dir / spec["parquet_path"]
            staging_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            parquet_path.parent.mkdir(parents=True, exist_ok=True)
            profile_outputs[profile_name] = stack.enter_context(staging_jsonl_path.open("w", encoding="utf-8"))
            profile_paths[profile_name] = {
                "staging_jsonl_path": staging_jsonl_path,
                "parquet_path": parquet_path,
            }

        for fp in get_dataset_connlu_files(stressed=True):
            source_file = fp.name
            context = {"newdoc_id": None, "newpar_id": None}
            for tokenlist in parse_incr(fp):
                update_context(context, tokenlist.metadata)
                row = sentence_row(tokenlist, source_file, context)
                source_dataset = row["source_dataset"]

                if source_dataset not in input_source_dataset_counters:
                    input_source_dataset_counters[source_dataset] = Counter()

                input_counter = input_source_dataset_counters[source_dataset]
                summary["input_row_count"] += 1
                input_counter["row_count"] += 1

                if not should_export_row(
                    row,
                    fully_stressed_only=fully_stressed_only,
                    exclude_number_sentences=exclude_number_sentences,
                ):
                    continue

                for profile_name in selected_profiles:
                    profile_row = row_for_profile(row, profile_name)
                    profile_outputs[profile_name].write(json.dumps(profile_row, ensure_ascii=False) + "\n")

                summary["row_count"] += 1

                if source_dataset not in source_dataset_counters:
                    source_dataset_counters[source_dataset] = Counter()

                counter = source_dataset_counters[source_dataset]
                counter["row_count"] += 1
                counter["token_count"] += row_word_token_count(row)
                counter["stressable_word_count"] += (
                    row["legacy_word_count"]
                    + row["cache_word_count"]
                    + row["vdu_nlp_services_word_count"]
                    + row["lki_words_word_count"]
                    + row["phonology_engine_word_count"]
                    + row["unresolved_word_count"]
                )
                counter["resolved_word_count"] += (
                    row["legacy_word_count"]
                    + row["cache_word_count"]
                    + row["vdu_nlp_services_word_count"]
                    + row["lki_words_word_count"]
                    + row["phonology_engine_word_count"]
                )
                counter["single_stress_option_word_count"] += row["single_stress_option_word_count"]
                counter["multiple_stress_option_word_count"] += row["multiple_stress_option_word_count"]
                counter["no_stress_option_word_count"] += row["no_stress_option_word_count"]
                counter["no_stress_option_with_tags_word_count"] += row["no_stress_option_with_tags_word_count"]
                counter["multiple_best_stress_option_word_count"] += row["multiple_best_stress_option_word_count"]
                counter["ambiguous_sentence_count"] += int(row_has_ambiguous_stress(row))
                counter["legacy_word_count"] += row["legacy_word_count"]
                counter["cache_word_count"] += row["cache_word_count"]
                counter["vdu_nlp_services_word_count"] += row["vdu_nlp_services_word_count"]
                counter["lki_words_word_count"] += row["lki_words_word_count"]
                counter["phonology_engine_word_count"] += row["phonology_engine_word_count"]
                counter["unresolved_word_count"] += row["unresolved_word_count"]
                counter["sktv_token_count"] += row["sktv_token_count"]
                counter["digit_token_count"] += row["digit_token_count"]
                counter["roman_numeral_token_count"] += row["roman_numeral_token_count"]
                for source_info in STRESS_SOURCE_INFO.values():
                    word_count_key = source_info["word_count_key"]
                    sentence_count_key = source_info["sentence_count_key"]
                    counter[sentence_count_key] += int(row[word_count_key] > 0)

    summary["by_source_dataset"] = {
        source_dataset: dict(counter)
        for source_dataset, counter in source_dataset_counters.items()
    }
    summary["input_by_source_dataset"] = {
        source_dataset: dict(counter)
        for source_dataset, counter in input_source_dataset_counters.items()
    }
    overall_counter = Counter()
    for counter in source_dataset_counters.values():
        overall_counter.update(counter)
    summary["overall"] = dict(overall_counter)

    for profile_name in selected_profiles:
        paths = profile_paths[profile_name]
        write_parquet_export(paths["staging_jsonl_path"], paths["parquet_path"])
        paths["staging_jsonl_path"].unlink(missing_ok=True)
        spec = EXPORT_PROFILE_SPECS[profile_name]
        summary["profiles"][profile_name] = {
            "hf_config_name": spec["hf_config_name"],
            "title": spec["title"],
            "description": spec["description"],
            "output_path": str(spec["parquet_path"]).replace(os.sep, "/"),
            "column_count": len(profile_columns[profile_name]),
            "columns": profile_columns[profile_name],
        }

    shutil.rmtree(output_dir / "_staging", ignore_errors=True)

    write_dataset_card(output_dir, summary)
    write_column_reference(output_dir, selected_profiles)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return output_dir, summary


def write_dataset_card(output_dir, summary):
    row_count = summary["row_count"]
    input_row_count = summary.get("input_row_count", row_count)
    omitted_row_count = input_row_count - row_count
    by_source_dataset = summary["by_source_dataset"]
    overall = summary.get("overall", {})
    selected_profiles = summary["selected_profiles"]
    profile_summaries = summary["profiles"]

    lines = [
        "---",
        "language:",
        "- lt",
        "license: cc-by-4.0",
        "pretty_name: %s" % DATASET_TITLE,
        "configs:",
    ]

    for profile_name in selected_profiles:
        profile_info = profile_summaries[profile_name]
        lines.extend([
            "- config_name: %s" % profile_info["hf_config_name"],
            "  data_files:",
            "  - split: train",
            "    path: %s" % profile_info["output_path"],
        ])

    lines.extend([
        "---",
        "",
        "# %s" % DATASET_TITLE,
        "",
        "Lithuanian sentences with word stress marks.",
        "",
        "The dataset combines MATAS v1.0 and ALKSNIS v3.0. It is useful for speech technology, pronunciation work, language learning, and research on Lithuanian stress.",
        "",
        "This release contains sentences where every Lithuanian word that needs stress has a selected stressed form. Sentences with Arabic or Roman numerals are left out because reading a number correctly depends on context and grammatical form.",
        "",
        "Some Lithuanian words allow more than one stress pattern. The dataset keeps the selected form and also records ambiguity counts. Here, *fully stressed* means that every applicable word has a selected form; it does not mean that every choice was unambiguous.",
        "",
        "## Quick Start",
        "",
        "```python",
        "from datasets import load_dataset",
        "",
        "dataset = load_dataset(\"meldynamics/lt-stressed-corpus\", \"default\")",
        "```",
        "",
    ])

    if len(selected_profiles) > 1:
        lines.extend([
            "## Choose a Config",
            "",
            "Both configs contain the same sentences:",
            "",
            "- `default`: recommended for most users; includes sentence text, tokens, and stress information.",
            "- `full`: also includes the original serialized CoNLL-U sentence and all sentence metadata.",
            "",
        ])
    else:
        profile_name = selected_profiles[0]
        lines.extend([
            "Published config:",
            "",
            "- `%s`: %s"
            % (profile_summaries[profile_name]["hf_config_name"], profile_summaries[profile_name]["description"]),
            "",
        ])

    lines.extend([
        "## What Is Included",
        "",
        "- `%s` sentences" % format_int(row_count),
        "- `%s` tokens" % format_int(overall.get("token_count", 0)),
        "- `%s` stressable words" % format_int(overall.get("stressable_word_count", 0)),
        "- `%s` unresolved stressable words in this export" % format_int(overall.get("no_stress_option_word_count", 0)),
        "- `%s` source sentences considered before filtering" % format_int(input_row_count),
        "- `%s` sentences omitted because they contain unresolved words, numbers, or both" % format_int(omitted_row_count),
        "",
        "The published data is a clean subset of the source corpora, not a complete export of every source sentence.",
        "",
        "## Sources",
        "",
    ])

    for source_dataset in ("alksnis", "matas"):
        source_info = SOURCE_DATASET_INFO[source_dataset]
        lines.append(
            "- [%s](%s): %s Used here for `%s` exported sentences."
            % (
                source_info["title"],
                source_info["url"],
                source_info["description"],
                format_int(by_source_dataset.get(source_dataset, {}).get("row_count", 0)),
            )
        )

    lines.extend([
        "",
        "## Data Origin and Stress Annotation",
        "",
        "The sentence text and linguistic annotation come from the MATAS v1.0 and ALKSNIS v3.0 CoNLL-U corpora. Their token forms, lemmas, and Jablonskis/XPOS morphology were retained; ALKSNIS dependency annotation was also preserved. The source corpora did not contain the stress marks added by this project.",
        "",
        "Most stress forms were added in the 2020 build by querying the former VDU Kirtis SOAP service for one word at a time (through the `vdu-nlp-services` Python client). Kirtis returned stressed alternatives with morphological labels. The builder converted those labels to the corpus tag vocabulary and selected the alternative with the same part of speech, the greatest tag overlap, and then the fewest extra tags. It used the existing MATAS/ALKSNIS morphology; it did not call a separate VDU morphology service or use sentence dependencies for disambiguation.",
        "",
        "VDU describes Kirtis as a morphology- and rule-based accentuator using Lemuoklis, syllabification, and lexical resources derived from Lithuanian dictionaries and accentuation references ([2005 report](https://sitti.vdu.lt/wp-content/uploads/2025/02/T_41_05_ataskaita.pdf); [2010 description](https://portalcris.vdu.lt/server/api/core/bitstreams/5e0a886f-e75c-4716-b7e7-a3c0ed837b9f/content)). If Kirtis did not supply a stressed form, the build tried an exact lookup in stressed entries collected from LKIIS dictionaries.",
        "",
        "The current release preserved `%s` forms from those 2020 stressed archives as `legacy`, added `%s` exact LKIIS-derived lookups, and added `%s` sentence-level fallbacks from [`phonology_engine`](https://github.com/aleksas/phonology_engine), derived from LIEPA-1. Because the old archives did not record a provider for each token, `legacy` usually means VDU-selected but can also include an older cache or dictionary fallback. The stress layer is automatic rather than exhaustively human-verified." % (
            format_int(overall.get("legacy_word_count", 0)),
            format_int(overall.get("lki_words_word_count", 0)),
            format_int(overall.get("phonology_engine_word_count", 0)),
        ),
        "",
        "The public export keeps only fully resolved sentences without Arabic or Roman numerals.",
    ])

    lines.extend([
        "",
        "## Main Fields",
        "",
        "- `original_text`: original sentence text",
        "- `stressed_text_unicode`: stressed sentence with Unicode combining stress marks",
        "- `tokens`: words and punctuation with linguistic analysis, stressed forms, and stress sources",
        "",
        "See [COLUMNS.md](./COLUMNS.md) for the complete field reference.",
        "",
        "## License",
        "",
        "The dataset files are published under [%s](%s). The current CLARIN-LT records list both source corpora under the same licence."
        % (SOURCE_DATASET_INFO["matas"]["license_name"], SOURCE_DATASET_INFO["matas"]["license_url"]),
        "",
        "- MATAS source page: [%s](%s)"
        % (SOURCE_DATASET_INFO["matas"]["title"], SOURCE_DATASET_INFO["matas"]["url"]),
        "- ALKSNIS source page: [%s](%s)"
        % (SOURCE_DATASET_INFO["alksnis"]["title"], SOURCE_DATASET_INFO["alksnis"]["url"]),
        "",
        "This derivative keeps the original sentence content and adds stress annotation. Please also credit the original corpora. Software used to build the data has separate terms; see the [`phonology_engine` licence and upstream attribution](https://github.com/aleksas/phonology_engine/blob/master/LICENSE).",
        "",
        "## Project",
        "",
        "Build scripts and source archives are maintained at [matas-alksnis-stressed](https://github.com/aleksas/matas-alksnis-stressed).",
        "",
        "## Citation",
        "",
        "```bibtex",
        "@misc{ltstressedcorpus,",
        "  title        = {LT Stressed Corpus},",
        "  author       = {Aleksas Pielikis},",
        "  year         = {2026},",
        "  note         = {Sentence-level Lithuanian corpus with Lithuanian word stress annotations},",
        "  howpublished = {Hugging Face dataset, MEL DYNAMICS}",
        "}",
        "```",
        "",
        "Also cite both original corpora below.",
        "",
        "- MATAS: %s" % SOURCE_DATASET_INFO["matas"]["citation"],
        "- ALKSNIS: %s" % SOURCE_DATASET_INFO["alksnis"]["citation"],
        "",
    ])

    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_column_reference(output_dir, selected_profiles):
    shared_column_descriptions = [
        ("source_dataset", "Short source name: `matas` or `alksnis`."),
        ("source_file", "Path of the sentence's CoNLL-U file inside the stressed archive tree."),
        ("sent_id", "Sentence identifier from the source metadata."),
        ("newdoc_id", "Current document identifier carried over from CoNLL-U metadata."),
        ("newpar_id", "Current paragraph identifier carried over from CoNLL-U metadata when present."),
        ("original_text", "Reconstructed original sentence text without added stress marks."),
        ("original_text_raw", "Raw source sentence text from metadata when available."),
        ("stressed_text_unicode", "Sentence text with Unicode combining stress marks."),
        ("sktv_token_count", "Count of tokens whose XPOS tag starts with `sktv.`."),
        ("digit_token_count", "Count of tokens containing Arabic digits."),
        ("roman_numeral_token_count", "Count of Roman numeral tokens recognized from `sktv.*` tags plus Roman-letter surface form."),
        ("tokens", "Full token records for every token entry in the CoNLL-U sentence."),
        ("single_stress_option_word_count", "Count of stressable words with exactly one available stress option."),
        ("multiple_stress_option_word_count", "Count of stressable words with multiple available stress options."),
        ("no_stress_option_word_count", "Count of stressable words with no accepted stress option."),
        ("no_stress_option_with_tags_word_count", "Count of words still unresolved even when tag-aware lookup information is available."),
        ("multiple_best_stress_option_word_count", "Count of words with more than one equally best stress option after ranking."),
        ("legacy_word_count", "Count of forms carried from the 2020 stressed archives. Repository history indicates that these were produced mainly from VDU Kirtis service variants selected with morphology-aware ranking; the old archives did not store token-level source labels."),
        ("cache_word_count", "Count of stressable words resolved from the local SQLite cache."),
        ("vdu_nlp_services_word_count", "Count of stressable words resolved through the VDU morphology-aware service path."),
        ("lki_words_word_count", "Count of stressable words resolved through the `lki.words` fallback."),
        ("phonology_engine_word_count", "Count of stressable words resolved through the final sentence-level LIEPA-style fallback."),
        ("unresolved_word_count", "Count of stressable words that remained unresolved in the exported sentence."),
        ("words_with_multiple_best_stress_options", "Word forms flagged as having multiple equally best stress choices."),
    ]
    full_only_column_descriptions = [
        ("conllu_sentence", "Serialized CoNLL-U sentence block for the exported row."),
        ("sentence_metadata", "Full sentence-level metadata map preserved from the stressed archive."),
    ]

    token_field_descriptions = [
        ("id", "Original token ID, preserved in JSON-safe form."),
        ("id_raw", "String form of the original token ID."),
        ("id_type", "Token ID category such as `word`, `multiword`, or `empty_node`."),
        ("form", "Surface form from the CoNLL-U token."),
        ("lemma", "Lemma from the CoNLL-U token."),
        ("upos", "UPOS tag."),
        ("xpos", "Original Jablonskis/XPOS tag."),
        ("feats", "Morphological feature map."),
        ("head", "Basic dependency head ID. Missing heads are exported as `-1`."),
        ("deprel", "Basic dependency relation label."),
        ("deps", "Enhanced dependency edges as `{deprel, head, raw}` objects."),
        ("misc", "CoNLL-U `misc` map."),
        ("stressed_form", "Chosen stressed form for the token, or the original form if none is stored."),
        ("stress_source", "Stage of the current rebuild that supplied the stored form. `legacy` identifies a form carried from the 2020 VDU-based build."),
        ("contains_digit", "Whether the token surface form contains an Arabic digit."),
        ("is_roman_numeral", "Whether the token is recognized as a Roman numeral under the export rules."),
        ("is_gap_token", "Whether the token is the `<g/>` gap marker."),
        ("is_word_token", "Whether the token has an integer CoNLL-U ID."),
    ]

    lines = [
        "# Column Reference",
        "",
        "This file documents the exported Hugging Face schema for `LT Stressed Corpus`.",
        "",
        "## Configs",
        "",
    ]

    for profile_name in selected_profiles:
        profile_info = EXPORT_PROFILE_SPECS[profile_name]
        lines.append(
            "- `%s`: %s `%s` top-level columns, file `%s`."
            % (
                profile_info["hf_config_name"],
                profile_info["description"],
                len(get_profile_field_order(profile_name)),
                profile_info["parquet_path"],
            )
        )

    lines.extend([
        "",
        "## Columns Shared By All Exported Configs",
        "",
    ])

    for name, description in shared_column_descriptions:
        lines.append("- `%s`: %s" % (name, description))

    if "full" in selected_profiles:
        lines.extend([
            "",
            "## Columns Only In `full`",
            "",
        ])
        for name, description in full_only_column_descriptions:
            lines.append("- `%s`: %s" % (name, description))

    lines.extend([
        "",
        "## `tokens[*]` Record Fields",
        "",
    ])

    for name, description in token_field_descriptions:
        lines.append("- `%s`: %s" % (name, description))

    (output_dir / "COLUMNS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def publish_dataset(output_dir, repo_id, private=False):
    from huggingface_hub import HfApi

    token = get_env_value("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN not found in environment or .env")

    output_dir = Path(output_dir)
    if not output_dir.exists():
        raise SystemExit("Export directory does not exist: %s" % output_dir)

    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True, private=private)
    repo_info = api.repo_info(repo_id=repo_id, repo_type="dataset")
    local_files = {
        str(path.relative_to(output_dir)).replace(os.sep, "/")
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    for sibling in repo_info.siblings:
        remote_path = sibling.rfilename
        if remote_path == ".gitattributes":
            continue
        if remote_path not in local_files:
            api.delete_file(
                path_in_repo=remote_path,
                repo_id=repo_id,
                repo_type="dataset",
                commit_message="Remove stale dataset artifact: %s" % remote_path,
            )
    api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(output_dir),
        path_in_repo=".",
    )


def build_parser():
    parser = argparse.ArgumentParser(description="Prepare and publish the stressed sentence dataset to Hugging Face.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export the current stressed archives as an HF-ready dataset folder.")
    export_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    export_parser.add_argument("--profile", default=DEFAULT_EXPORT_PROFILE, choices=["all", "default", "full", "public"])
    export_parser.add_argument("--include-unresolved", action="store_true")
    export_parser.add_argument("--include-number-sentences", action="store_true")

    publish_parser = subparsers.add_parser("publish", help="Upload an exported dataset folder to Hugging Face.")
    publish_parser.add_argument("--repo-id", default=get_env_value("HF_DATASET_REPO_ID"))
    publish_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    publish_parser.add_argument("--profile", default=DEFAULT_EXPORT_PROFILE, choices=["all", "default", "full", "public"])
    publish_parser.add_argument("--private", action="store_true")
    publish_parser.add_argument("--skip-export", action="store_true")
    publish_parser.add_argument("--include-unresolved", action="store_true")
    publish_parser.add_argument("--include-number-sentences", action="store_true")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "export":
        output_dir, summary = export_dataset(
            args.output_dir,
            fully_stressed_only=not args.include_unresolved,
            exclude_number_sentences=not args.include_number_sentences,
            profile=args.profile,
        )
        print(
            "Exported %d rows to %s for profile(s): %s"
            % (summary["row_count"], output_dir, ", ".join(summary["selected_profiles"]))
        )
        return

    if not args.repo_id:
        raise SystemExit("Provide --repo-id or set HF_DATASET_REPO_ID in .env")

    if not args.skip_export:
        output_dir, summary = export_dataset(
            args.output_dir,
            fully_stressed_only=not args.include_unresolved,
            exclude_number_sentences=not args.include_number_sentences,
            profile=args.profile,
        )
        print(
            "Exported %d rows to %s for profile(s): %s"
            % (summary["row_count"], output_dir, ", ".join(summary["selected_profiles"]))
        )

    publish_dataset(args.output_dir, args.repo_id, private=args.private)
    print("Uploaded dataset folder %s to %s" % (args.output_dir, args.repo_id))


if __name__ == "__main__":
    main()
