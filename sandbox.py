from vdu_nlp_services import stress_word
from zipfile import ZipFile
from conllu import parse_incr
from io import TextIOWrapper
import tag_map
import re

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

def get_tokenlists():
	for fp in get_dataset_connlu_files():
		for tokenlist in parse_incr(fp):
			yield tokenlist

def get_stessed_sentences():
	for tokenlist in get_tokenlists():
		offset = 0
		text = tokenlist.metadata['text']
		text_word_spans = []
		stressed_text = ''
		stressed_text_word_spans = []
		
		for token in tokenlist:
			word = token['form']

			word_offset = text.find(word, offset)
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

			stressed_text_word_spans.append( (len(stressed_text), len(stressed_text) + len(stress_options[0][1])) )
			stressed_text += stress_options[0][1]

			offset = word_offset + len(word)

		glue = text[offset:]
		stressed_text += glue

		tokenlist.metadata['stressed_text'] = stressed_text
		tokenlist.metadata['text_word_spans'] = ','.join(['%d:%d' % span for span in text_word_spans])
		tokenlist.metadata['stressed_text_word_spans'] = ','.join(['%d:%d' % span for span in stressed_text_word_spans])

		yield (
			tokenlist.metadata['text'],
			tokenlist.metadata['stressed_text'],
			tokenlist.metadata['text_word_spans'],
			tokenlist.metadata['stressed_text_word_spans']
		)

for sentence in get_stessed_sentences():
	print(sentence)
	print()
