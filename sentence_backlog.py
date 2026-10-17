import argparse
import json
from collections import Counter
from pathlib import Path

from conllu import parse_incr

from archive_iterator import get_dataset_connlu_files


DEFAULT_OUTPUT_DIR = Path('sentence_backlog_lt_stressed')
DEFAULT_DATA_PATH = Path('backlog.jsonl')


def normalize_sentence_text(text):
	if not text:
		return ''
	return text.rstrip()


def reconstruct_sentence(tokenlist, stressed=False):
	parts = []
	for token in tokenlist:
		token_id = token['id']
		if not isinstance(token_id, int):
			continue

		form = token['form']
		if form == '<g/>':
			continue

		if stressed:
			form = (
				token.get('misc', {}).get('StressedForm')
				if token.get('misc')
				else None
			) or form

		parts.append(form)

		no_space_after = False
		try:
			no_space_after = token['misc']['SpaceAfter'] == 'No'
		except (TypeError, KeyError):
			no_space_after = False

		if not no_space_after:
			parts.append(' ')

	return normalize_sentence_text(''.join(parts))


def parse_int_metadata(metadata, key):
	value = metadata.get(key)
	return int(value) if value else 0


def get_source_dataset_name(source_file):
	if source_file.startswith('MATAS-v1.0-stressed/'):
		return 'matas'
	if source_file.startswith('Alksnis-3.0-stressed/'):
		return 'alksnis'
	raise ValueError('Unknown stressed source path: %s' % source_file)


def get_source_dataset_version(source_file):
	if source_file.startswith('MATAS-v1.0-stressed/'):
		return 'MATAS-v1.0'
	if source_file.startswith('Alksnis-3.0-stressed/'):
		return 'Alksnis-3.0'
	raise ValueError('Unknown stressed source path: %s' % source_file)


def sentence_backlog_row(tokenlist, source_file):
	metadata = tokenlist.metadata
	single = parse_int_metadata(metadata, 'single_stress_option_word_count')
	multiple = parse_int_metadata(metadata, 'multiple_stress_option_word_count')
	no_stress = parse_int_metadata(metadata, 'no_stress_option_word_count')
	no_stress_with_tags = parse_int_metadata(metadata, 'no_stress_option_with_tags_word_count')
	multiple_best = parse_int_metadata(metadata, 'multiple_best_stress_option_word_count')

	evaluable_word_count = single + multiple + no_stress
	resolved_word_count = evaluable_word_count - no_stress
	ambiguous_word_count = multiple
	token_count = sum(
		1 for token in tokenlist
		if isinstance(token['id'], int) and token['form'] != '<g/>'
	)

	completion_ratio = 1.0
	if evaluable_word_count:
		completion_ratio = resolved_word_count / evaluable_word_count

	return {
		'row_id': '%s:%s' % (get_source_dataset_name(source_file), metadata['sent_id']),
		'source_dataset': get_source_dataset_name(source_file),
		'source_dataset_version': get_source_dataset_version(source_file),
		'source_file': source_file,
		'sent_id': metadata['sent_id'],
		'newdoc_id': metadata.get('newdoc id'),
		'newpar_id': metadata.get('newpar id'),
		'original_text': normalize_sentence_text(
			metadata.get('sentence_rebuilt') or reconstruct_sentence(tokenlist, stressed=False)
		),
		'stressed_text': normalize_sentence_text(
			metadata.get('stressed_sentence') or reconstruct_sentence(tokenlist, stressed=True)
		),
		'token_count': token_count,
		'evaluable_word_count': evaluable_word_count,
		'resolved_word_count': resolved_word_count,
		'ambiguous_word_count': ambiguous_word_count,
		'single_stress_option_word_count': single,
		'multiple_stress_option_word_count': multiple,
		'no_stress_option_word_count': no_stress,
		'no_stress_option_with_tags_word_count': no_stress_with_tags,
		'multiple_best_stress_option_word_count': multiple_best,
		'completion_ratio': round(completion_ratio, 6),
		'is_complete': no_stress == 0,
		'is_unambiguous': no_stress == 0 and multiple == 0,
	}


def backlog_sort_key(row):
	return (
		row['no_stress_option_word_count'],
		row['ambiguous_word_count'],
		-row['completion_ratio'],
		row['token_count'],
		row['row_id'],
	)


def build_backlog(incomplete_only=False):
	rows = []
	summary = {
		'row_count': 0,
		'incomplete_row_count': 0,
		'complete_row_count': 0,
		'unambiguous_complete_row_count': 0,
		'by_source_dataset': {},
	}
	source_dataset_counters = {}

	for fp in get_dataset_connlu_files(stressed=True):
		source_file = fp.name
		for tokenlist in parse_incr(fp):
			row = sentence_backlog_row(tokenlist, source_file)
			source_dataset = row['source_dataset']

			if source_dataset not in source_dataset_counters:
				source_dataset_counters[source_dataset] = Counter()

			counter = source_dataset_counters[source_dataset]
			counter['row_count'] += 1
			counter['complete_row_count'] += 1 if row['is_complete'] else 0
			counter['incomplete_row_count'] += 0 if row['is_complete'] else 1
			counter['unambiguous_complete_row_count'] += 1 if row['is_unambiguous'] else 0
			counter['unresolved_word_count'] += row['no_stress_option_word_count']
			counter['ambiguous_word_count'] += row['ambiguous_word_count']

			summary['row_count'] += 1
			summary['complete_row_count'] += 1 if row['is_complete'] else 0
			summary['incomplete_row_count'] += 0 if row['is_complete'] else 1
			summary['unambiguous_complete_row_count'] += 1 if row['is_unambiguous'] else 0

			if incomplete_only and row['is_complete']:
				continue

			rows.append(row)

	rows.sort(key=backlog_sort_key)

	for index, row in enumerate(rows, start=1):
		row['backlog_rank'] = index

	summary['exported_row_count'] = len(rows)
	summary['by_source_dataset'] = {
		source_dataset: dict(counter)
		for source_dataset, counter in source_dataset_counters.items()
	}

	return rows, summary


def export_backlog(output_dir, incomplete_only=False):
	output_dir = Path(output_dir)
	output_path = output_dir / DEFAULT_DATA_PATH
	output_dir.mkdir(parents=True, exist_ok=True)

	rows, summary = build_backlog(incomplete_only=incomplete_only)

	with output_path.open('w', encoding='utf-8') as fp:
		for row in rows:
			fp.write(json.dumps(row, ensure_ascii=False) + '\n')

	(output_dir / 'summary.json').write_text(
		json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
		encoding='utf-8',
	)

	return output_path, summary


def main():
	parser = argparse.ArgumentParser(
		description='Export stressed sentence completion backlog sorted by unresolved load.'
	)
	parser.add_argument(
		'command',
		nargs='?',
		default='export',
		choices=['export'],
	)
	parser.add_argument('--output-dir', default=DEFAULT_OUTPUT_DIR)
	parser.add_argument('--incomplete-only', action='store_true')
	args = parser.parse_args()

	output_path, summary = export_backlog(
		args.output_dir,
		incomplete_only=args.incomplete_only,
	)

	print(
		'Wrote %d backlog rows to %s'
		% (summary['exported_row_count'], output_path)
	)


if __name__ == '__main__':
	main()
