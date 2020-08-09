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

tag_pattern = re.compile(r'([\w-]+\.)|(kita)')

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

def parse_jablonskis_tag_string(tag_string):
	for k, v in tag_map.fix_jablonskis_string.items():
		tag_string = tag_string.replace(k, v)

	for m in tag_pattern.finditer(tag_string):
		tag = m.group(0)
		
		if tag in tag_map.fix_jablonskis_tag_map_key_set:
			tag = tag_map.fix_jablonskis_tag_map[tag]

		yield tag

def get_sorted_stress_options(word, tag_string):
	if tag_string:
		jablonskis_tags = list(parse_jablonskis_tag_string(tag_string))
		jablonskis_tag_set = set(jablonskis_tags)
		
		invalid_jablonskis_tags = jablonskis_tag_set.difference(tag_map.valid_jablonskis_tag_set)
		if len(invalid_jablonskis_tags):
			raise Exception()
		stress_options = []
		
		max_converted_stress_tag_set_length = 0

		for stressed_word, stress_tags in stress_word(word):
			stress_tags = list(stress_tags)
			
			converted_stress_tags = list(tag_map.convert_kirtis_to_jablonskis_tags(stress_tags, jablonskis_tag_set))
			converted_stress_tag_set = set(converted_stress_tags)

			if tag_map.missing_tags:
				print ('\n'.join(tag_map.missing_tags))

			converted_stress_tag_difference_set = converted_stress_tag_set.difference( jablonskis_tag_set )

			if converted_stress_tags and converted_stress_tags[0] not in tag_map.jablonskis_categories:
				raise Exception()

			if jablonskis_tags:
				jablonskis_category_tag = jablonskis_tags[0] if not jablonskis_tags[0] == 'sampl.' else jablonskis_tags[1]
				if jablonskis_category_tag in tag_map.jablonskis_verb_form_tag_replacements:
					
					jablonskis_tags.insert(jablonskis_tags.index(jablonskis_category_tag), tag_map.jablonskis_verb_form_tag_replacements[jablonskis_category_tag][0])
					jablonskis_category_tag = tag_map.jablonskis_verb_form_tag_replacements[jablonskis_category_tag][0]
				if jablonskis_category_tag not in tag_map.jablonskis_categories:
					raise Exception()
			else:
				jablonskis_category_tag = None

			category_match = 1 if converted_stress_tags and converted_stress_tags[0] == jablonskis_category_tag else 0

			max_converted_stress_tag_set_length = max(max_converted_stress_tag_set_length, len(converted_stress_tag_set))

			val = category_match, len(converted_stress_tag_set) - len(converted_stress_tag_difference_set), len(converted_stress_tag_set)
			
			stress_options.append( (val, stressed_word, converted_stress_tags, jablonskis_tags) )

		stress_options.sort(key=lambda a: (a[0][0], a[0][1], max_converted_stress_tag_set_length - a[0][2]), reverse=True)			
		
		return stress_options, ''.join(jablonskis_tags), jablonskis_tags
	else:
		return [], tag_string, []

def stessed_sentence(tokenlist, conn):
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

	for i, token in enumerate(tokenlist):
		word = token['form']
		if word == '<g/>':
			remove_tokens.append(token)
			continue
		
		sorted_stress_options, tag_string, jablonskis_tags = get_sorted_stress_options(word, token['xpos'] if 'xpos' in token else '')
		if tag_string:
			token['xpos'] = tag_string
		
		stressed_word = sorted_stress_options[0][1]
		if stressed_word:
			if 'misc' not in token or not token['misc']:
				token['misc'] = OrderedDict([('StressedForm', stressed_word)])
			else:
				token['misc'].update([('StressedForm', stressed_word)])
				
		lemma = token['lemma'] if 'lemma' in token else None
		word_stress_db.add(conn, word, stressed_word, lemma, jablonskis_tags)

		sentence += word
		stressed_sentence += stressed_word

		if 'misc' in token and token['misc'] and 'SpaceAfter' in token['misc']:
			if token['misc']['SpaceAfter'] == 'No':
				sentence += ''
		else:
			sentence += ' '
			stressed_sentence += ' '

		update_stress_stats(stress_stats, word, sorted_stress_options, jablonskis_tags)

	for token in remove_tokens:
		tokenlist.remove(token)
	
	tokenlist.metadata['stressed_sentence'] = stressed_sentence
	tokenlist.metadata['sentence_rebuilt'] = sentence
	
	for k,v in stress_stats.items():
		val = str(v) if isinstance(v, int) else ','.join(v) # Either int or set of strings
		if val:
			tokenlist.metadata[k] = val

def stessed_sentences():
	with word_stress_db.init('stress.sqlite.db') as conn:
		for fp in get_dataset_connlu_files():
			os.makedirs(os.path.dirname(fp.name), exist_ok=True)
			if not os.path.exists(fp.name):
				tmp_name = fp.name + '.tmp'
				with open(tmp_name, 'wt', encoding=fp.encoding) as fpw:
					for tokenlist in parse_incr(fp):
						stessed_sentence(tokenlist, conn)
						fpw.write(tokenlist.serialize())

						for k, v in tokenlist.metadata.items():
							print (k, v)
						print()
				os.rename(tmp_name, fp.name)
				conn.commit()

if __name__ == '__main__':
	stessed_sentences()
