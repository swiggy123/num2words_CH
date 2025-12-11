import unittest
from num2words.detect_convert_ch_numbers import convert_numbers


class TestCHBSConversion(unittest.TestCase):
    """Test CH_BS (Basel-Stadt) number to words conversion."""

    def setUp(self):
        """Set up test fixtures."""
        self.dialect = "ch_bs"

    def test_simple_numbers(self):
        """Test conversion of simple plain numbers."""
        self.assertEqual(convert_numbers("Ich habe 5 Äpfel.", self.dialect), 
                        "Ich habe fünf Äpfel.")
        self.assertEqual(convert_numbers("Es gibt 42 Personen.", self.dialect),
                        "Es gibt zweiävierzig Personen.")
        self.assertEqual(convert_numbers("Die Zahl ist 100.", self.dialect),
                        "Die Zahl ist eihundärd.")

    def test_ordinal_numbers(self):
        """Test conversion of ordinal numbers."""
        self.assertEqual(convert_numbers("Das ist der 1. Platz.", self.dialect),
                        "Das ist der erst Platz.")
        self.assertEqual(convert_numbers("Die 2. Person kommt.", self.dialect),
                        "Die zweit Person kommt.")
        self.assertEqual(convert_numbers("Das ist der 3. Tag.", self.dialect),
                        "Das ist der dritt Tag.")

    def test_ordinal_at_sentence_end(self):
        """Test that numbers at end of sentence are not treated as ordinals."""
        # "Die Antwort ist 2." - the 2. is just a number at end, not an ordinal
        result = convert_numbers("Die Antwort ist 2.", self.dialect)
        # Should treat "2" as plain number, not ordinal
        self.assertIn("zwei", result)

    def test_years(self):
        """Test conversion of years."""
        self.assertEqual(convert_numbers("Das Jahr 2024.", self.dialect),
                        "Das Jahr zweitusigvieräzwanzig.")
        self.assertEqual(convert_numbers("Im Jahr 1999.", self.dialect),
                        "Im Jahr nünzäh nünänünzig.")

    def test_zip_codes(self):
        """Test conversion of Swiss ZIP codes."""
        # 4410 is a valid Swiss ZIP code
        self.assertIn("PLZ vierävierzig zäh", convert_numbers("PLZ 4410", self.dialect))

    def test_phone_numbers(self):
        """Test conversion of phone numbers."""
        result = convert_numbers("Tel: +41 23 056 789", self.dialect)
        self.assertEqual("Tel: plus vier eis zwei drei null fünf sechs siebe acht nün", result)

    def test_mixed_content(self):
        """Test conversion of text with multiple number types."""
        text = "Der 2. Termin ist am 15. Januar im Jahr 1983."
        result = convert_numbers(text, self.dialect)
        self.assertEqual("Der zweit Termin ist am füfzähnt Januar im Jahr nünzäh dreiäachzig.", result)


    def test_no_numbers(self):
        """Test that text without numbers is unchanged."""
        text = "Dies ist ein einfacher Text ohne Zahlen."
        result = convert_numbers(text, self.dialect)
        self.assertEqual(text, result)

    def test_multiple_same_numbers(self):
        """Test conversion of multiple occurrences of same number."""
        text = "Ich habe 5 Äpfel und 5 Birnen."
        result = convert_numbers(text, self.dialect)
        self.assertEqual(result, "Ich habe fünf Äpfel und fünf Birnen.")

    def test_large_numbers(self):
        """Test conversion of large numbers."""
        self.assertIn("million", convert_numbers("Die Bevölkerung: 1000000.", self.dialect).lower())


if __name__ == "__main__":
    unittest.main()
