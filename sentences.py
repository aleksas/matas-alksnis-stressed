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
				
				space_after = True
				if 'misc' in token and token['misc'] and 'SpaceAfter' in token['misc']:
					if token['misc']['SpaceAfter'] == 'No':
						space_after = False

				if space_after:
					sentence += ' '

			yield sentence.rstrip()

if __name__ == '__main__':
	for sentence in get_sentences():
		print(sentence)
