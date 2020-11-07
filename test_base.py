#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest import TestCase, main
from stress_sentences import get_sorted_stress_options

class SimpleTestCase(TestCase):
    def test_3(self):
        sorted_stress_options = get_sorted_stress_options(None, 'atrinkti', 'atrinkti', 'vksm.dlv.neveik.būt.vyr.dgs.V.', complex_ranking=True)

        self.assertEqual(sorted_stress_options[0][2], ['dlv.', 'vyr.', 'būt.', 'dgs.', 'V.', 'neveik.'])        
        self.assertEqual(sorted_stress_options[0][1], 'atrinkti`')

if __name__ == '__main__':
    main()