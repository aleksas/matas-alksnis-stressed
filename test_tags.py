from vdu_nlp_services import stress_word
from multext_east_jablonskis_convertor import get_jablonskis_tags
from zipfile import ZipFile
from conllu import parse_incr
from io import TextIOWrapper
import re

matas_archive_filename = './dataset/MATAS-v1.0.zip'

matas_conllu_filename_pattern = re.compile(r'MATAS-v1\.0\/CONLLU\/.*\.conllu')
tag_pattern = re.compile(r'[\w-]+\.')

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
            sentence_parts = []
            
            for token in tokenlist:
                word = token['form']

                word_offset = sentence.find(word, offset)
                
                glue = sentence[offset: word_offset]
            
                if glue:
                    sentence_parts.append( (glue, glue) )
                    
                matas_tag_set = set([])
                for tag in tag_pattern.finditer(token['xpos']):
                    matas_tag_set.add(tag.group(0))

                stress_options = []
                word_stress_option = stress_options[0][1] if stress_options else word
                sentence_parts.append( (word, word_stress_option) )

                multext = token['misc']['Multext']
                jablonskis_tags = None
                try:
                    jablonskis_tags = get_jablonskis_tags(multext)
                except Exception as e:
                    #print(e)
                    pass
                jablonskis_tag_set = set(jablonskis_tags)
                if matas_tag_set.difference(jablonskis_tag_set):
                    print (','.join([tokenlist.metadata['sent_id'], word, multext, ' '.join(jablonskis_tag_set), ' '.join(matas_tag_set)]))
                    print()

                offset = word_offset + len(word)

            glue = sentence[offset:]

            if glue:
                sentence_parts.append( (glue, glue) )

            yield sentence_parts

for sentence in get_stessed_sentences():
	print(sentence)
	print()
