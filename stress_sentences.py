from vdu_nlp_services import stress_word
from zipfile import ZipFile
from conllu import parse_incr
from io import TextIOWrapper
import tag_map
import re
import os

datasets = [
	('./datasets/Alksnis-3.0.zip', re.compile(r'Alksnis-3.0\/.*\.conllu')),
	('./datasets/MATAS-v1.0.zip', re.compile(r'MATAS-v1\.0\/CONLLU\/.*\.conllu'))
]

tag_pattern = re.compile(r'[\w-]+\.')

def get_dataset_connlu_files(encoding='utf-8'):
	for archive_filename, conllu_filename_pattern in datasets:
		with ZipFile(archive_filename, 'r') as zip_ref:
			for filename in zip_ref.namelist():
				if conllu_filename_pattern.match(filename):
					with zip_ref.open(filename, 'r') as fp:
						with TextIOWrapper(fp, encoding=encoding) as text_fp:
							yield text_fp

def update_stress_stats(stress_stats, word, sorted_stress_options):
	stress_option_count = len(set([s for _,s in sorted_stress_options]))
	limited_stress_option_count = len(set([s for v,s in sorted_stress_options if v == sorted_stress_options[0][0]]))

	single_stress_option = stress_option_count == 1
	multiple_stress_options = stress_option_count > 1
	no_stress_options = len(sorted_stress_options) == 0
	multiple_options_with_min_count = stress_option_count > 1 and limited_stress_option_count > 1

	stress_stats['single_stress_option'] += 1 if single_stress_option else 0
	stress_stats['multiple_stress_options'] += 1 if multiple_stress_options else 0
	stress_stats['no_stress_options'] += 1 if no_stress_options else 0
	stress_stats['multiple_options_with_min_count'] += 1 if multiple_options_with_min_count else 0

	if multiple_options_with_min_count:
		stress_stats['words_multiple_options_with_min_count'].add(word)

def stessed_sentence(tokenlist):
	offset = 0
	text = tokenlist.metadata['text']
	text_word_spans = []
	stressed_text = ''
	stressed_text_word_spans = []
	
	stress_stats = {	
		'single_stress_option': 0,
		'multiple_stress_options': 0,
		'no_stress_options': 0,
		'multiple_options_with_min_count': 0,
		'words_multiple_options_with_min_count': set([])
	}
	
	for token in tokenlist:
		word = token['form']

		word_offset = text.find(word, offset)
		if word_offset == -1:
			raise Exception('"%s" not found within the sentece "%s"' % (word, text))

		text_word_spans.append( (word_offset, word_offset + len(word)) )
		
		glue = text[offset: word_offset]
		stressed_text += glue
			
		jablonskis_tag = []
		if 'xpos' in token:
			for tag in tag_pattern.finditer(token['xpos']):
				jablonskis_tag.append(tag.group(0))
		jablonskis_tag_set = set(jablonskis_tag)

		stress_options = []
		for stressed_word, stress_tags in stress_word(word):
			stress_tags = list(stress_tags)
			stress_tag_set = set(stress_tags)
			
			converted_stress_tags = tag_map.convert_kirtis_to_jablonskis_tags(stress_tag_set, jablonskis_tag_set)
			if tag_map.missing_tags:
				print ('\n'.join(tag_map.missing_tags))

			converted_stress_tag_difference_set = set(converted_stress_tags).difference( jablonskis_tag_set )
			stress_options.append( (len(converted_stress_tag_difference_set), stressed_word) )

		stress_options.sort(key=lambda a: a[0])

		update_stress_stats(stress_stats, word, stress_options)

		stressed_text_word_spans.append( (len(stressed_text), len(stressed_text) + len(stress_options[0][1])) )
		stressed_text += stress_options[0][1]

		offset = word_offset + len(word)

	glue = text[offset:]
	stressed_text += glue

	tokenlist.metadata['stressed_text'] = stressed_text
	tokenlist.metadata['text_word_spans'] = ','.join(['%d:%d' % span for span in text_word_spans])
	tokenlist.metadata['stressed_text_word_spans'] = ','.join(['%d:%d' % span for span in stressed_text_word_spans])

	for k,v in stress_stats.items():
		val = str(v) if isinstance(v, int) else ','.join(v) # Either int or set of strings
		if val:
			tokenlist.metadata[k] = val

def stessed_sentences(encoding='utf-8'):
	for fp in get_dataset_connlu_files(encoding=encoding):
		os.makedirs(os.path.dirname(fp.name), exist_ok=True)
		with open(fp.name, 'wt', encoding=encoding) as fpw:
			for tokenlist in parse_incr(fp):
				stessed_sentence(tokenlist)
				fpw.write(tokenlist.serialize())

if __name__ == '__main__':
	stessed_sentences()
