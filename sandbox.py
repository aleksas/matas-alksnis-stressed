from vdu_nlp_services import stress_text
from zipfile import ZipFile
from conllu import parse_incr
from io import TextIOWrapper
import re

matas_archive_filename = './dataset/MATAS-v1.0.zip'

stress_pattern = re.compile(r'(\d+\.)\s+([^\(]+)\s+\(([^\)]+)\)')
matas_conllu_filename_pattern = re.compile(r'MATAS-v1\.0\/CONLLU\/.*\.conllu')

def stress(word):
	res = stress_text(word.strip()).splitlines()

	for line in res:
		m = stress_pattern.match(line)
		if m:
			word = m.group(2)
			details = m.group(3).split(' ')
			yield {'word': word, 'details': details}
		else:
			yield {'word': word, 'details': []}

def get_dataset_connlu_files(encoding='utf-8'):
	with ZipFile(matas_archive_filename, 'r') as zip_ref:
		for filename in zip_ref.namelist():
			if matas_conllu_filename_pattern.match(filename):
				with zip_ref.open(filename, 'r') as fp:
					with TextIOWrapper(fp, encoding=encoding) as text_fp:
						yield text_fp

def get_stessed_sentences():
	for fp in get_dataset_connlu_files():
		for tokenlist in parse_incr(fp):
			offset = 0
			sentence = tokenlist.metadata['text']
			stressed_sentence = ''
			
			for token in tokenlist:
				tags = token['xpos']
				word = token['form']

				word_offset = sentence.find(word, offset)
				stressed_sentence += sentence[offset: word_offset]

				offset = word_offset + len(word)

				for each in stress(word):
					stressed_sentence += each['word']
					# TODO: add mapping VDU stress to MATAS tags
					# subtract setts, stress with smallest set size should be selected
					break
			
			stressed_sentence += sentence[offset:]

			yield sentence, stressed_sentence #, (tokenlist.metadata['sent_id'], tokenlist.metadata['newpar id'], tokenlist.metadata['newdoc id'])

for sentence, stressed_sentence in get_stessed_sentences():
	print(sentence)
	print(stressed_sentence)
	print()