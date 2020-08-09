from archive_iterator import get_dataset_connlu_files
from conllu import parse_incr
import re

def get_sentences():
	for fp in get_dataset_connlu_files():
		for tokenlist in parse_incr(fp):
			sentence = ''
			for token in tokenlist:
				if token['form'] == '<g/>':
					continue
				
				sentence += token['form']
				
				try:
					no_space_after = token['misc']['SpaceAfter'] == 'No'
				except (TypeError, KeyError):
					no_space_after = False

				if not no_space_after:
					sentence += ' '

			yield sentence.rstrip()

if __name__ == '__main__':
	for sentence in get_sentences():
		print(sentence)
