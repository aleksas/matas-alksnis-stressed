from vdu_nlp_services import stress_word
from zipfile import ZipFile
from io import TextIOWrapper
import re

datasets = [
	('./datasets/Alksnis-3.0.zip', re.compile(r'Alksnis-3.0\/.*\.conllu'), 'utf-8'),
	('./datasets/MATAS-v1.0.zip', re.compile(r'MATAS-v1\.0\/CONLLU\/.*\.conllu'), 'utf-8')
]

def get_dataset_connlu_files():
	for archive_filename, conllu_filename_pattern, encoding in datasets:
		with ZipFile(archive_filename, 'r') as zip_ref:
			for filename in zip_ref.namelist():
				if conllu_filename_pattern.match(filename):
					with zip_ref.open(filename, 'r') as fp:
						with TextIOWrapper(fp, encoding=encoding) as text_fp:
							yield text_fp