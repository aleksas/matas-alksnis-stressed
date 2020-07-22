from vdu_nlp_services import stress_text
from zipfile import ZipFile
from os.path import isdir
from shutil import rmtree
import re

matas_archive_filename = './dataset/MATAS-v1.0.zip'
matas_target_directory = './dataset/'
matas_extracted_directory = matas_target_directory + '/MATAS-v1.0'

pattern = re.compile(r'(\d+)\.\s+([^\(]+)\s*\(([^\)]+)\)')


def stress(word):
	res = stress_text(word.strip()).splitlines()

	if len(res) == 1:
		yield {'word': res[0].strip(), 'details': []}
	else:
		for line in res:
			m = pattern.match(line)
			if m:
				yield {'word': m.group(2), 'details': m.group(3).split(' ')}
			else:
				raise Exception()

def unpack(force=False):
	dir_exists = isdir(matas_extracted_directory)
	if force and dir_exists:
		rmtree(matas_extracted_directory)
		dir_exists = False

	if not dir_exists:
		with ZipFile(matas_archive_filename, 'r') as zip_ref:
			zip_ref.extractall(matas_target_directory)

unpack()

res = stress('keliai')
for r in res:
	print (r)
