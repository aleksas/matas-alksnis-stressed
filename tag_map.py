matas_stress_tag_pairs = [
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
	('kuopin.', ''),
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

matas_stress_opposite_tag_pairs = [
    ('įvardž.', 'neįvardž.'),
    ('sngr.', 'nesngr.')
]

stress_matas_tag_map = { s:m for m, s in matas_stress_tag_pairs }
stress_matas_tag_map.update( { s: None for _, s in matas_stress_opposite_tag_pairs } )

missing_tags = set([])

def convert_stress_to_matas_tags(stress_tags, matas_tags=None):
	skip = False
	if matas_tags:
		for matas_oposite_tag, stress_oposite_tag in matas_stress_opposite_tag_pairs:
			if stress_oposite_tag in stress_tags and matas_oposite_tag in matas_tags:
				# Skip tags if obviously wrong
				skip = True
	
	if not skip:
		for tag in stress_tags:
			if tag not in stress_matas_tag_map:
				missing_tags.add(tag)
			else:
				if stress_matas_tag_map[tag]:
					mapped_tag = stress_matas_tag_map[tag]
					if mapped_tag:
						yield mapped_tag