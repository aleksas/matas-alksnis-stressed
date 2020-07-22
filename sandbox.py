from vdu_nlp_services import stress_text
from zipfile import ZipFile
from conllu import parse_incr
from io import TextIOWrapper
import re

matas_archive_filename = './dataset/MATAS-v1.0.zip'

stress_pattern = re.compile(r'(\d+)\.\s+([^\(]+)\s*\(([^\)]+)\)')
matas_conllu_filename_pattern = re.compile(r'MATAS-v1\.0\/CONLLU\/.*\.conllu')

def stress(word):
	res = stress_text(word.strip()).splitlines()

	if len(res) == 1:
		yield {'word': res[0].strip(), 'details': []}
	else:
		for line in res:
			m = stress_pattern.match(line)
			if m:
				yield {'word': m.group(2), 'details': m.group(3).split(' ')}
			else:
				raise Exception()

def dataset_connlu_files(encoding='utf-8'):
	with ZipFile(matas_archive_filename, 'r') as zip_ref:
		for filename in zip_ref.namelist():
			if matas_conllu_filename_pattern.match(filename):
				with zip_ref.open(filename, 'r') as fp:
					with TextIOWrapper(fp, encoding=encoding) as text_fp:
						yield text_fp

res = stress('keliai')
for r in res:
	print (r)


for fp in dataset_connlu_files():
	for tokenlist in parse_incr(fp):
		print(tokenlist)
