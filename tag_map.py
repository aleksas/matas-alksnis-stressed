fix_jablonskis_string = {
	'būt.k.': 'būt-k.',
	'~DEM.': ''
}

fix_complete_jablonskis_string = {
	'sktv.arab': 'sktv.arab.',
}

fix_jablonskis_tag_map = {
	'dktv.': 'dkt.',
	'samp.': 'sampl.',
	'kiekin.': 'kiek.',
	'kita.': 'kita',
	'būts.': 'būt.',
	'padlv.': 'pad.',
	'Įv.': 'Įn.',
	'vt.': 'Vt.',
	'būdv.': 'bdv.',
	'nelyg.': 'nelygin.',
	'neygin.': 'nelygin.',
	'v.':'V.'
}
fix_jablonskis_tag_map_key_set = set(fix_jablonskis_tag_map.keys())

jablonskis_verb_form_tag_replacements = {
    'dlv.': ['vksm.', 'dlv.'],
    'pad.': ['vksm.', 'pad..'],
    'pusd.': ['vksm.', 'pusd.'],
    'būdn.': ['vksm.', 'būdn.']
}

missing_tags = set([])
