from morpho_tagsets_lt.kirtis_jablonskis import valid_jablonskis_tag_set, jablonskis_categories
from morpho_tagsets_lt import sort_jablonskis_tags, kirtis_to_jablonskis_tags
from archive_iterator import get_dataset_connlu_files
from vdu_nlp_services import soap_stressor
from vdu_nlp_services import stress_word
from collections import OrderedDict
from conllu import parse_incr
import word_stress_db
import tag_map
import re
import os
import json
import lki

tag_pattern = re.compile(r'([\w-]+\.)|(kita)')
ascii2utf8_map = {v:lki.chars.utf8_stress_map[k] for k,v in lki.chars.ascii_stress_map.items()}

def update_stress_stats(stress_stats, word, sorted_stress_options, jablonskis_tags):
	stress_option_count = len(set([s for _,s,_,_ in sorted_stress_options if s != word]))
	limited_stress_option_count = len(set([s for v,s,_,_ in sorted_stress_options if s != word and v == sorted_stress_options[0][0]]))

	single_stress_option = stress_option_count == 1
	multiple_stress_options = stress_option_count > 1
	no_stress_options = stress_option_count == 0
	no_stress_option_with_tags_word_count = stress_option_count == 0 and len(jablonskis_tags) > 2
	multiple_min_diff_stress_options = stress_option_count > 1 and limited_stress_option_count > 1

	stress_stats['single_stress_option_word_count'] += 1 if single_stress_option else 0
	stress_stats['multiple_stress_option_word_count'] += 1 if multiple_stress_options else 0
	stress_stats['no_stress_option_word_count'] += 1 if no_stress_options else 0
	stress_stats['no_stress_option_with_tags_word_count'] += 1 if no_stress_option_with_tags_word_count else 0
	stress_stats['multiple_best_stress_option_word_count'] += 1 if multiple_min_diff_stress_options else 0

	if multiple_min_diff_stress_options:
		stress_stats['words_with_multiple_best_stress_options'].add(word)

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
		for k,v in ascii2utf8_map.items():
			stressed_word = stressed_word.replace(k, v)
		lki.chars.utf8_stress_map
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
		
		stressed_word += (chunk.upper() if u else chunk)
		offset += len(chunk)
		
	return stressed_word

def stessed_sentence(tokenlist, conn, words):
	sentence = ''
	stressed_sentence = ''

	stress_stats = {	
		'single_stress_option_word_count': 0,
		'multiple_stress_option_word_count': 0,
		'no_stress_option_word_count': 0,
		'no_stress_option_with_tags_word_count': 0,
		'multiple_best_stress_option_word_count': 0,
		'words_with_multiple_best_stress_options': set([])
	}
	
	remove_tokens = []

	for token in tokenlist:
		word = token['form']
		if word == '<g/>':
			remove_tokens.append(token)
			continue
	
		if 'xpos' in token:
			tag_string = token['xpos']
		elif 'xpostag' in token:
			tag_string = token['xpostag']
		else:
			tag_string = None
		exceptions = ['skyr.', 'kita', 'kita.', 'sktv.arab.', 'sktv.rom.', 'sktv.mišr.', 'akr.', 'sutr.', 'užs.']
		arabic_numeral = tag_string == 'sktv.' and re.match(r'^\d+$', word)
		roman_numeral = tag_string == 'sktv.' and re.match(r'^[IVMCDX]+$', word)
		if tag_string and tag_string not in exceptions and not arabic_numeral and not roman_numeral:				
			jablonskis_tags = parse_jablonskis_tag_string(tag_string)

			new_tag_string = ''.join(jablonskis_tags)
			if new_tag_string:
				token['xpos'] = new_tag_string
				
			lemma = token['lemma'] if 'lemma' in token else None
			stressed_word = word_stress_db.stress(conn, word, lemma, jablonskis_tags)
			if not stressed_word:
				sorted_stress_options = get_sorted_stress_options(conn, word, lemma, jablonskis_tags)

				stressed_word = sorted_stress_options[0][1]
				if stressed_word != word:
					if 'misc' not in token or not token['misc']:
						token['misc'] = OrderedDict([('StressedForm', stressed_word)])
					else:
						token['misc'].update([('StressedForm', stressed_word)])

				update_stress_stats(stress_stats, word, sorted_stress_options, jablonskis_tags)
			
			if word == stressed_word:
				try:
					word_lower = word.lower()
					stressed_word_lower = words[word_lower]
					stressed_word = recover_capitalization(word, stressed_word_lower)

				except:
					with open('unstressed.txt', 'at', encoding='utf-8') as fp:
						fp.write( '%s %s\n' % (word, tag_string) )
					print(word, tag_string)
		else:
			stressed_word = word
			
		sentence += word
		stressed_sentence += stressed_word

		if 'misc' in token and token['misc'] and 'SpaceAfter' in token['misc']:
			if token['misc']['SpaceAfter'] == 'No':
				sentence += ''
		else:
			sentence += ' '
			stressed_sentence += ' '


	for token in remove_tokens:
		tokenlist.remove(token)
	
	tokenlist.metadata['stressed_sentence'] = stressed_sentence
	tokenlist.metadata['sentence_rebuilt'] = sentence
	
	for k,v in stress_stats.items():
		val = str(v) if isinstance(v, int) else ','.join(v) # Either int or set of strings
		if val:
			tokenlist.metadata[k] = val

def stessed_sentences():
	words = {}
	for word, unstressed in lki.words.get_word_pairs(lki.words.get_words()):
		words[unstressed] = word

	with word_stress_db.init('stress.sqlite.db') as conn:
		for fp in get_dataset_connlu_files():
			os.makedirs(os.path.dirname(fp.name), exist_ok=True)
			if not os.path.exists(fp.name):
				tmp_name = fp.name + '.tmp'
				with open(tmp_name, 'wt', encoding=fp.encoding) as fpw:
					for tokenlist in parse_incr(fp):
						stessed_sentence(tokenlist, conn, words)
						fpw.write(tokenlist.serialize())

				os.rename(tmp_name, fp.name)
				conn.commit()

if __name__ == '__main__':
	stessed_sentences()
