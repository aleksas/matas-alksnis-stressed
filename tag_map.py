jablonskis_kirtis_tag_pairs = [
	('1', 'Iasm.'),
	('2', 'IIasm.'),
	('3', 'IIIasm.'),
	('akr.', ''),
	('arab.', ''),
	('asm.', ''),
	('aukšč.', ''),
	('aukšt.', ''),
	('bdv.', 'bdvr.'),
	('bendr.', 'bendr.gim.'),
	('bev.', 'bevrd.gim.'),
	('bndr.', ''),
	('būdn.', 'būdn.'),
	('būs.', 'būs.l.'),
	('būt-d.', 'būt.d.l.'),
	('būt-k', 'būt.kart.l.'),
	('būt.', 'būt.l.'),
	('daugin.', 'daugin.'),
	('dgs.', 'dgsk.'),
	('dkt.', 'dktv.'),
	('dll.', 'dll.'),
	('dlv.', 'dlv.'),
	('dvisk.', 'dvisk.'),
	('es.', 'esam.l.'),
	('G.', 'G.'),
	('Il.', 'Vt(ev).'),
	('Įn.', 'Įn.'),
	('išt.', 'ištk.'),
	('įv.', 'įvrd.'),
	('įvardž.', 'įvardž.'),
	('jng.', 'jngt.'),
	('jst.', 'jstk.'),
	('K.', 'K.'),
	('kelint.', 'kelintin.'),
	('kiek.', 'kiekin.'),
	('kita', ''),
	('kuopin.', 'kuopin.'),
	('liep.', ''),
	('mišr.', ''),
	('mot.', 'mot.gim.'),
	('N.', 'N.'),
	('neig.', ''),
	('nelygin.', ''),
	('neveik.', 'neveik.r.'),
	('pad.', 'padlv.'),
	('prl.', 'prln.'),
	('prv.', 'prvks.'),
	('pusd.', 'psdlv.'),
	('raid.', ''),
	('reik.', 'reikiamyb.'),
	('rom.', ''),
	('Š.', 'Š.'),
	('sampl.', ''),
	('sktv.', 'sktv.'),
	('skyr.', ''),
	('sngr.', 'sngr.'),
	('sutr.', 'sutrmp.'),
	('tar.', ''),
	('tęs.', ''),
	('tiesiog.', ''),
	('tikr.', 'T.'),
	('užs.', ''),
	('V.', 'V.'),
	('veik.', 'veik.r.'),
	('vksm.', 'vksm.'),
	('vns.', 'vnsk.'),
	('Vt.', 'Vt.'),
	('vyr.', 'vyr.gim.'),
]

jablonskis_kirtis_opposite_tag_pairs = [
    ('įvardž.', 'neįvardž.'),
    ('sngr.', 'nesngr.')
]

kirtis_jablonskis_tag_map = { s:m for m, s in jablonskis_kirtis_tag_pairs }
kirtis_jablonskis_tag_map.update( { s: None for _, s in jablonskis_kirtis_opposite_tag_pairs } )

missing_tags = set([])

def convert_kirtis_to_jablonskis_tags(kirtis_tags, jablonskis_tags=None):
	skip = False
	if jablonskis_tags:
		for jablonskis_oposite_tag, kirtis_oposite_tag in jablonskis_kirtis_opposite_tag_pairs:
			if kirtis_oposite_tag in kirtis_tags and jablonskis_oposite_tag in jablonskis_tags:
				# Skip tags if obviously wrong
				skip = True
	
	if not skip:
		for tag in kirtis_tags:
			if tag not in kirtis_jablonskis_tag_map:
				missing_tags.add(tag)
			else:
				if kirtis_jablonskis_tag_map[tag]:
					mapped_tag = kirtis_jablonskis_tag_map[tag]
					if mapped_tag:
						yield mapped_tag