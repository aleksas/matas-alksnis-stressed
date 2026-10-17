import argparse
from collections import Counter, OrderedDict
import os
import re

import lki
import tag_map
import word_stress_db
from archive_iterator import get_dataset_connlu_files, get_stressed_output_path
from conllu import parse_incr
from morpho_tagsets_lt import kirtis_to_jablonskis_tags, sort_jablonskis_tags
from morpho_tagsets_lt.kirtis_jablonskis import (
	jablonskis_categories,
	valid_jablonskis_tag_set,
)
from vdu_nlp_services import stress_word

tag_pattern = re.compile(r'([\w-]+\.)|(kita)')
ascii2utf8_map = {v: lki.chars.utf8_stress_map[k] for k, v in lki.chars.ascii_stress_map.items()}

stress_char_pattern = re.compile(r'[\u0300\u0301\u0303`~^]')
letter_pattern = re.compile(r'[A-Za-zĄ-Žą-ž]')
digit_pattern = re.compile(r'\d')
roman_numeral_pattern = re.compile(r'^[IVXLCDM]+$', re.IGNORECASE)

stressable_tag_exceptions = {
	'skyr.',
	'kita',
	'kita.',
	'sktv.arab.',
	'sktv.rom.',
	'sktv.mišr.',
	'akr.',
	'sutr.',
	'užs.',
}

stress_source_metadata_key = 'StressSource'
stress_source_count_keys = {
	'legacy': 'legacy_word_count',
	'cache': 'cache_word_count',
	'vdu-nlp-services': 'vdu_nlp_services_word_count',
	'lki.words': 'lki_words_word_count',
	'phonology_engine': 'phonology_engine_word_count',
	'unresolved': 'unresolved_word_count',
}
stress_stat_int_keys = (
	'single_stress_option_word_count',
	'multiple_stress_option_word_count',
	'no_stress_option_word_count',
	'no_stress_option_with_tags_word_count',
	'multiple_best_stress_option_word_count',
)
stress_stat_set_keys = (
	'words_with_multiple_best_stress_options',
)

_phonology_engine_instance = None
_phonology_engine_import_error = None
_phonology_engine_import_reported = False


def get_stress_option_summary(word, sorted_stress_options, jablonskis_tags):
	if sorted_stress_options:
		best_value = sorted_stress_options[0][0]
	else:
		best_value = None

	stress_option_count = len(set([s for _, s, _, _ in sorted_stress_options if s != word]))
	limited_stress_option_count = len(
		set([s for v, s, _, _ in sorted_stress_options if s != word and v == best_value])
	)

	return {
		'single_stress_option': stress_option_count == 1,
		'multiple_stress_options': stress_option_count > 1,
		'no_stress_options': stress_option_count == 0,
		'no_stress_option_with_tags': stress_option_count == 0 and len(jablonskis_tags) > 2,
		'multiple_min_diff_stress_options': stress_option_count > 1 and limited_stress_option_count > 1,
	}


def update_stress_stats(stress_stats, word, option_summary):
	stress_stats['single_stress_option_word_count'] += 1 if option_summary['single_stress_option'] else 0
	stress_stats['multiple_stress_option_word_count'] += 1 if option_summary['multiple_stress_options'] else 0
	stress_stats['no_stress_option_word_count'] += 1 if option_summary['no_stress_options'] else 0
	stress_stats['no_stress_option_with_tags_word_count'] += 1 if option_summary['no_stress_option_with_tags'] else 0
	stress_stats['multiple_best_stress_option_word_count'] += 1 if option_summary['multiple_min_diff_stress_options'] else 0

	if option_summary['multiple_min_diff_stress_options']:
		stress_stats['words_with_multiple_best_stress_options'].add(word)


def decrement_unresolved_stats(stress_stats, option_summary):
	if not option_summary or not option_summary['no_stress_options']:
		return

	stress_stats['no_stress_option_word_count'] -= 1
	if option_summary['no_stress_option_with_tags']:
		stress_stats['no_stress_option_with_tags_word_count'] -= 1

def fix_jablonskis_tag_string(tag_string):
	for k, v in tag_map.fix_jablonskis_string.items():
		tag_string = tag_string.replace(k, v)
	for k, v in tag_map.fix_complete_jablonskis_string.items():
		if tag_string == k:
			tag_string = v
	return tag_string

def parse_jablonskis_tag_string(tag_string):
	tag_string = fix_jablonskis_tag_string(tag_string)

	tags = []
	for m in tag_pattern.finditer(tag_string):
		tag = m.group(0)
		
		if tag in tag_map.fix_jablonskis_tag_map_key_set:
			tag = tag_map.fix_jablonskis_tag_map[tag]

		tags.append(tag)
	
	sort_jablonskis_tags(tags)

	return tags

def stress_word_jablonskis(conn, word, lemma):
	for stressed_word, stress_tags in stress_word(word):
		for k, v in ascii2utf8_map.items():
			stressed_word = stressed_word.replace(k, v)
		stress_tags = list(stress_tags)
		
		jablonskis_tags = list(kirtis_to_jablonskis_tags(stress_tags))

		word_stress_db.add(conn, word, stressed_word, jablonskis_tags)
		word_stress_db.update_lemma(conn, word, lemma, stressed_word, jablonskis_tags)

		yield stressed_word, jablonskis_tags

def get_sorted_stress_options(conn, word, lemma, jablonskis_tags):
	jablonskis_tag_set = set(jablonskis_tags)
	
	invalid_jablonskis_tags = jablonskis_tag_set.difference(valid_jablonskis_tag_set)
	if len(invalid_jablonskis_tags):
		raise Exception()
	stress_options = []
	
	max_converted_stress_tag_set_length = 0

	for stressed_word, jablonskis_stress_tags in stress_word_jablonskis(conn, word, lemma):
		jablonskis_stress_tag_set = set(jablonskis_stress_tags)

		if tag_map.missing_tags:
			print ('\n'.join(tag_map.missing_tags))

		converted_stress_tag_difference_set = jablonskis_stress_tag_set.difference( jablonskis_tag_set )

		if jablonskis_stress_tags and jablonskis_stress_tags[0] not in jablonskis_categories:
			raise Exception()

		if jablonskis_tags:
			jablonskis_category_tag = jablonskis_tags[0] if not jablonskis_tags[0] == 'sampl.' else jablonskis_tags[1]
			if jablonskis_category_tag in tag_map.jablonskis_verb_form_tag_replacements:
				
				jablonskis_tags.insert(jablonskis_tags.index(jablonskis_category_tag), tag_map.jablonskis_verb_form_tag_replacements[jablonskis_category_tag][0])
				jablonskis_category_tag = tag_map.jablonskis_verb_form_tag_replacements[jablonskis_category_tag][0]
			if jablonskis_category_tag not in jablonskis_categories:
				raise Exception()
		else:
			jablonskis_category_tag = None

		category_match = 1 if jablonskis_stress_tags and jablonskis_stress_tags[0] == jablonskis_category_tag else 0

		max_converted_stress_tag_set_length = max(max_converted_stress_tag_set_length, len(jablonskis_stress_tag_set))

		val = category_match, len(jablonskis_stress_tag_set) - len(converted_stress_tag_difference_set), len(jablonskis_stress_tag_set)
		
		stress_options.append( (val, stressed_word, jablonskis_stress_tags, jablonskis_tags) )

	stress_options.sort(key=lambda a: (a[0][0], a[0][1], max_converted_stress_tag_set_length - a[0][2]), reverse=True)
	
	return stress_options

def recover_capitalization(word, stressed_word_lower):
	stressed_word = ''
	offset = 0
	for l in word:
		u = l.isupper()
		k = stressed_word_lower[offset:].find(l.lower())
		chunk = stressed_word_lower[offset: offset + k + 1]
		offset += len(chunk)
		while offset < len(stressed_word_lower) and stress_char_pattern.match(stressed_word_lower[offset]):
			chunk += stressed_word_lower[offset]
			offset += 1
		
		stressed_word += (chunk.upper() if u else chunk)
		
	return stressed_word

def strip_stress_marks(text):
	return stress_char_pattern.sub('', text)


def has_stress_mark(text):
	return bool(text and stress_char_pattern.search(text))


def get_token_tag_string(token):
	if 'xpos' in token:
		return token['xpos']
	if 'xpostag' in token:
		return token['xpostag']
	return None


def set_token_tag_string(token, tag_string):
	if 'xpostag' in token or 'upostag' in token:
		token['xpostag'] = tag_string
	else:
		token['xpos'] = tag_string


def is_stressable_token(word, tag_string):
	if not tag_string or tag_string in stressable_tag_exceptions:
		return False

	arabic_numeral = tag_string == 'sktv.' and re.match(r'^\d+$', word)
	roman_numeral = tag_string == 'sktv.' and roman_numeral_pattern.match(word)
	return not arabic_numeral and not roman_numeral


def ensure_token_misc(token):
	misc = token.get('misc')
	if misc:
		if isinstance(misc, OrderedDict):
			return misc
		return OrderedDict(misc)
	return OrderedDict()


def apply_token_resolution(token, stressed_word, source):
	misc = ensure_token_misc(token)

	if stressed_word and stressed_word != token['form']:
		misc['StressedForm'] = stressed_word
	else:
		misc.pop('StressedForm', None)

	if source:
		misc[stress_source_metadata_key] = source
	else:
		misc.pop(stress_source_metadata_key, None)

	token['misc'] = misc if misc else None


def get_existing_stressed_word(token):
	misc = token.get('misc')
	if not misc:
		return None

	stressed_word = misc.get('StressedForm')
	if not stressed_word:
		return None
	if strip_stress_marks(stressed_word).lower() != token['form'].lower():
		return None
	return stressed_word if has_stress_mark(stressed_word) else None


def get_existing_stress_source(token):
	misc = token.get('misc')
	if not misc:
		return None
	return misc.get(stress_source_metadata_key)


def create_stress_stats():
	return {
		'single_stress_option_word_count': 0,
		'multiple_stress_option_word_count': 0,
		'no_stress_option_word_count': 0,
		'no_stress_option_with_tags_word_count': 0,
		'multiple_best_stress_option_word_count': 0,
		'words_with_multiple_best_stress_options': set([]),
	}


def load_existing_stress_stats(tokenlist):
	stress_stats = create_stress_stats()
	for metadata_key in stress_stat_int_keys:
		value = tokenlist.metadata.get(metadata_key)
		stress_stats[metadata_key] = int(value) if value else 0

	for metadata_key in stress_stat_set_keys:
		value = tokenlist.metadata.get(metadata_key)
		if value:
			stress_stats[metadata_key] = set([word for word in value.split(',') if word])

	return stress_stats


def write_stress_stats(tokenlist, stress_stats):
	for metadata_key in stress_stat_int_keys:
		tokenlist.metadata[metadata_key] = str(stress_stats[metadata_key])

	for metadata_key in stress_stat_set_keys:
		values = sorted(stress_stats[metadata_key])
		if values:
			tokenlist.metadata[metadata_key] = ','.join(values)
		else:
			tokenlist.metadata.pop(metadata_key, None)


def build_legacy_unresolved_option_summary(jablonskis_tags):
	return {
		'single_stress_option': False,
		'multiple_stress_options': False,
		'no_stress_options': True,
		'no_stress_option_with_tags': len(jablonskis_tags) > 2,
		'multiple_min_diff_stress_options': False,
	}


def get_phonology_engine():
	global _phonology_engine_instance
	global _phonology_engine_import_error
	global _phonology_engine_import_reported

	if _phonology_engine_instance is False:
		if not _phonology_engine_import_reported:
			print('phonology_engine unavailable: %s' % _phonology_engine_import_error)
			_phonology_engine_import_reported = True
		return None

	if _phonology_engine_instance is None:
		try:
			from phonology_engine import PhonologyEngine
		except ImportError as exc:
			_phonology_engine_instance = False
			_phonology_engine_import_error = exc
			return get_phonology_engine()

		_phonology_engine_instance = PhonologyEngine()

	return _phonology_engine_instance


def build_sentence_text(token_infos):
	parts = []
	offset = 0
	remove_tokens = []

	for token_info in token_infos:
		token = token_info['token']
		word = token_info['word']

		if word == '<g/>':
			remove_tokens.append(token)
			continue

		start = offset
		parts.append(word)
		offset += len(word)
		token_info['source_span'] = (start, offset)

		no_space_after = False
		try:
			no_space_after = token['misc']['SpaceAfter'] == 'No'
		except (TypeError, KeyError):
			no_space_after = False

		if not no_space_after:
			parts.append(' ')
			offset += 1

	return ''.join(parts).rstrip(), remove_tokens


def get_source_span(letter_map, word_span):
	if not word_span or word_span[1] <= word_span[0]:
		return None

	start = letter_map[word_span[0]]
	end = letter_map[word_span[1] - 1] + 1
	return start, end


def normalize_phonology_stressed_word(word, stressed_word):
	if not stressed_word:
		return None

	if strip_stress_marks(stressed_word).lower() != word.lower():
		return None

	normalized = recover_capitalization(word, stressed_word.lower())
	return normalized if has_stress_mark(normalized) else None


def sentence_has_unhandled_numbers(token_infos):
	for token_info in token_infos:
		word = token_info['word']
		tag_string = token_info['tag_string']

		if digit_pattern.search(word):
			return True

		if tag_string == 'sktv.' and roman_numeral_pattern.fullmatch(word):
			return True

	return False


def apply_phonology_engine_fallback(token_infos, sentence, stress_stats):
	phonology_engine = get_phonology_engine()
	if not phonology_engine or not sentence.strip():
		return
	if sentence_has_unhandled_numbers(token_infos):
		return

	pending_by_span = {}
	for token_info in token_infos:
		if token_info['source'] != 'unresolved':
			continue
		if not token_info['is_stressable']:
			continue
		if not token_info.get('source_span'):
			continue
		if not letter_pattern.search(token_info['word']):
			continue

		pending_by_span[token_info['source_span']] = token_info

	if not pending_by_span:
		return

	try:
		processed_sentences = list(phonology_engine.process(sentence))
	except Exception as exc:
		print('phonology_engine sentence processing failed: %s' % exc)
		return

	for word_details, _, _, letter_map in processed_sentences:
		for word_detail in word_details:
			source_span = get_source_span(letter_map, word_detail.get('word_span'))
			if not source_span:
				continue

			token_info = pending_by_span.get(source_span)
			if not token_info:
				continue

			stressed_word = normalize_phonology_stressed_word(
				token_info['word'],
				word_detail.get('utf8_stressed_word'),
			)
			if not stressed_word:
				continue

			token_info['stressed_word'] = stressed_word
			token_info['source'] = 'phonology_engine'
			decrement_unresolved_stats(stress_stats, token_info['option_summary'])


def log_unresolved_token(token_info):
	with open('unstressed.txt', 'at', encoding='utf-8') as fp:
		fp.write('%s %s\n' % (token_info['word'], token_info['tag_string']))


def resolve_token(token, conn, words, stress_stats, allow_vdu=True, preserve_existing_stress=False):
	word = token['form']
	tag_string = get_token_tag_string(token)
	is_stressable = is_stressable_token(word, tag_string)
	token_info = {
		'token': token,
		'word': word,
		'stressed_word': word,
		'source': None,
		'tag_string': tag_string,
		'is_stressable': is_stressable,
		'option_summary': None,
		'source_span': None,
	}

	if word == '<g/>':
		return token_info

	if not is_stressable:
		return token_info

	if preserve_existing_stress:
		existing_stressed_word = get_existing_stressed_word(token)
		if existing_stressed_word:
			token_info['stressed_word'] = existing_stressed_word
			token_info['source'] = get_existing_stress_source(token) or 'legacy'
			return token_info

	jablonskis_tags = parse_jablonskis_tag_string(tag_string)
	token_info['jablonskis_tags'] = jablonskis_tags

	new_tag_string = ''.join(jablonskis_tags)
	if new_tag_string:
		set_token_tag_string(token, new_tag_string)

	if preserve_existing_stress:
		token_info['option_summary'] = build_legacy_unresolved_option_summary(jablonskis_tags)

	lemma = token['lemma'] if 'lemma' in token else None
	stressed_word = word_stress_db.stress(conn, word, lemma, jablonskis_tags)
	if stressed_word:
		token_info['stressed_word'] = stressed_word
		token_info['source'] = 'cache'
		decrement_unresolved_stats(stress_stats, token_info['option_summary'])
		return token_info

	if allow_vdu:
		sorted_stress_options = get_sorted_stress_options(conn, word, lemma, jablonskis_tags)
		option_summary = get_stress_option_summary(word, sorted_stress_options, jablonskis_tags)
		token_info['option_summary'] = option_summary
		update_stress_stats(stress_stats, word, option_summary)

		if sorted_stress_options:
			stressed_word = sorted_stress_options[0][1]
			if stressed_word != word:
				token_info['stressed_word'] = stressed_word
				token_info['source'] = 'vdu-nlp-services'
				return token_info

	word_lower = word.lower()
	stressed_word_lower = words.get(word_lower)
	if stressed_word_lower:
		token_info['stressed_word'] = recover_capitalization(word, stressed_word_lower)
		token_info['source'] = 'lki.words'
		decrement_unresolved_stats(stress_stats, token_info['option_summary'])
		return token_info

	token_info['source'] = 'unresolved'
	return token_info


def finalize_token_resolution(token_info):
	if token_info['source'] == 'unresolved':
		log_unresolved_token(token_info)

	if token_info['is_stressable']:
		apply_token_resolution(token_info['token'], token_info['stressed_word'], token_info['source'])


def build_stressed_sentence(token_infos):
	parts = []
	for token_info in token_infos:
		token = token_info['token']
		word = token_info['word']
		if word == '<g/>':
			continue

		parts.append(token_info['stressed_word'])

		no_space_after = False
		try:
			no_space_after = token['misc']['SpaceAfter'] == 'No'
		except (TypeError, KeyError):
			no_space_after = False

		if not no_space_after:
			parts.append(' ')

	return ''.join(parts).rstrip()


def update_resolution_source_stats(tokenlist, token_infos):
	source_counts = Counter()
	for token_info in token_infos:
		if not token_info['is_stressable']:
			continue
		if token_info['source'] in stress_source_count_keys:
			source_counts[stress_source_count_keys[token_info['source']]] += 1

	for metadata_key in stress_source_count_keys.values():
		tokenlist.metadata[metadata_key] = str(source_counts.get(metadata_key, 0))


def stessed_sentence(tokenlist, conn, words, allow_vdu=True, preserve_existing_stress=False):
	sentence = ''
	stress_stats = load_existing_stress_stats(tokenlist) if preserve_existing_stress else create_stress_stats()

	token_infos = [
		resolve_token(
			token,
			conn,
			words,
			stress_stats,
			allow_vdu=allow_vdu,
			preserve_existing_stress=preserve_existing_stress,
		)
		for token in tokenlist
	]
	sentence, remove_tokens = build_sentence_text(token_infos)
	apply_phonology_engine_fallback(token_infos, sentence, stress_stats)

	for token_info in token_infos:
		finalize_token_resolution(token_info)

	stressed_sentence = build_stressed_sentence(token_infos)

	for token in remove_tokens:
		tokenlist.remove(token)
	
	tokenlist.metadata['stressed_sentence'] = stressed_sentence
	tokenlist.metadata['sentence_rebuilt'] = sentence
	update_resolution_source_stats(tokenlist, token_infos)
	write_stress_stats(tokenlist, stress_stats)

def stessed_sentences(input_stressed=False, overwrite=False):
	words = {}
	for word, unstressed in lki.words.get_word_pairs(lki.words.get_words()):
		words[unstressed] = word

	with word_stress_db.init('stress.sqlite.db') as conn:
		for fp in get_dataset_connlu_files(stressed=input_stressed):
			output_name = get_stressed_output_path(fp.name)
			os.makedirs(os.path.dirname(output_name), exist_ok=True)
			if not overwrite and os.path.exists(output_name):
				continue

			tmp_name = output_name + '.tmp'
			with open(tmp_name, 'wt', encoding=fp.encoding) as fpw:
				for tokenlist in parse_incr(fp):
					stessed_sentence(
						tokenlist,
						conn,
						words,
						allow_vdu=not input_stressed,
						preserve_existing_stress=input_stressed,
					)
					fpw.write(tokenlist.serialize())

			os.replace(tmp_name, output_name)
			conn.commit()


def build_parser():
	parser = argparse.ArgumentParser(description='Generate stressed CoNLL-U outputs.')
	parser.add_argument(
		'--input-stressed',
		action='store_true',
		help='Reuse the existing stressed archives as input and only re-resolve unresolved tokens.',
	)
	parser.add_argument(
		'--overwrite',
		action='store_true',
		help='Overwrite extracted stressed output files if they already exist.',
	)
	return parser

if __name__ == '__main__':
	args = build_parser().parse_args()
	stessed_sentences(input_stressed=args.input_stressed, overwrite=args.overwrite)
