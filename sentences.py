from archive_iterator import get_dataset_connlu_files
from conllu import parse_incr

def get_sentences(stressed=False):
	for fp in get_dataset_connlu_files():
		for tokenlist in parse_incr(fp):
			sentence = ''
			for token in tokenlist:
				form = token['misc']['StressedForm'] if stressed and 'misc' in token and token['misc'] and 'StressedForm' in token['misc']  else token['form'] 
				if form == '<g/>':
					continue
				
				sentence += form
				
				try:
					no_space_after = token['misc']['SpaceAfter'] == 'No'
				except (TypeError, KeyError):
					no_space_after = False

				if not no_space_after:
					sentence += ' '

			yield sentence

if __name__ == '__main__':
	for sentence in get_sentences(True):
		print(sentence)
