#!/usr/bin/env python
# -*- coding: utf-8 -*-

from unittest import TestCase, main
from stress_sentences import get_sorted_stress_options

class SimpleTestCase(TestCase):
    def test_1(self):
        sorted_stress_options = get_sorted_stress_options('turi', 'vksm.asm.es.3.tiesiog.')

        sorted_stress_option = sorted_stress_options[0][2]

        self.assertEqual(sorted_stress_option, ['vksm.', 'es.', '3.', 'vns.'])        
        self.assertEqual(sorted_stress_options[0][1], 'tu`ri')

    def test_2(self):
        sorted_stress_options = get_sorted_stress_options('negali', 'vksm.asm.es.3.tiesiog.neig.')

        sorted_stress_option = sorted_stress_options[0][2]

        self.assertEqual(sorted_stress_option, ['vksm.', 'es.', '3.', 'vns.'])        
        self.assertEqual(sorted_stress_options[0][1], 'nega~li')

if __name__ == '__main__':
    main()