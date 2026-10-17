import unittest

from hf_dataset import is_roman_numeral_token


class RomanNumeralTokenTest(unittest.TestCase):
    def test_upper_case_roman_numerals(self):
        for form in ("I", "IV", "XIX", "XXI"):
            self.assertTrue(is_roman_numeral_token({"form": form, "xpos": "sktv.rom."}), form)

    def test_numeral_words_spelled_with_roman_letters(self):
        for form in ("dvi", "Dvi"):
            self.assertFalse(is_roman_numeral_token({"form": form, "xpos": "sktv.kiek.mot.G."}), form)

    def test_requires_numeral_tag(self):
        self.assertFalse(is_roman_numeral_token({"form": "XI", "xpos": "dkt.vyr.vns.V."}))


if __name__ == "__main__":
    unittest.main()
