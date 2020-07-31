from zipfile import ZipFile
from conllu import parse_incr
from io import TextIOWrapper
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

def get_sentences(encoding='utf-8'):
	for fp in get_dataset_connlu_files(encoding=encoding):
		for tokenlist in parse_incr(fp):
			yield tokenlist.metadata['text']

for sentence in get_sentences():
	print(sentence)
