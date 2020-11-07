from archive_iterator import get_dataset_connlu_files
from conllu import parse_incr

def get_sentences(stressed=False):
	for fp in get_dataset_connlu_files():
		first_tokenlist = True
		for tokenlist in parse_incr(fp):
			first_token = True
			sentence = ''
			for token in tokenlist:
				if not first_token or not first_tokenlist and tokenlist.metadata['newpar id']:
					sentence += '\n'

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

			first_token = False			
		first_tokenlist = False

if __name__ == '__main__':
	for sentence in get_sentences(True):
		print(sentence)
