"""Synthetic regression tests: never print raw source identifiers."""
import sys
from pathlib import Path
import unittest
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from privacy_preview import safe_preview, redact_text_for_review


class PrivacyPreviewTests(unittest.TestCase):
    def test_contact_patterns(self):
        examples = ['example@example.com', '0412 345 678', '+61 412 345 678', '(02) 9000 1234', '02 9000 1234', '+61 2 9000 1234', '+61 (0) 412 345 678']
        for token in examples:
            with self.subTest(kind='contact'):
                self.assertNotIn(token, redact_text_for_review('Contact ' + token))

    def test_registrations(self):
        for token in ['ABC123', '123ABC', 'AB12CD', 'ABC12D']:
            self.assertNotIn(token, redact_text_for_review('Car ' + token))
            self.assertNotIn(token, redact_text_for_review('rego: ' + token))

    def test_known_name_boundaries(self):
        self.assertEqual(redact_text_for_review('Ask Example Person.', ['Example Person']), 'Ask [PERSON].')
        self.assertEqual(redact_text_for_review('Marked improvement', ['Mark']), 'Marked improvement')

    def test_unknown_name_is_not_claimed_safe(self):
        # Redaction is expressly heuristic. Default preview must withhold the whole comment.
        self.assertEqual(redact_text_for_review('Ask Unlisted Person'), 'Ask Unlisted Person')
        g = pd.DataFrame([['Comments'], ['Ask Unlisted Person at 99 Example Street']])
        self.assertEqual(safe_preview(g).iloc[1, 0], '[TEXT WITHHELD]')

    def test_identity_columns_including_staff(self):
        for header in ['Name', 'Customer', 'Cust No', 'dms_customer_no', 'Rego', 'Email', 'Phone', 'Staff', 'Taken by', 'Card given by', 'Logged by', 'Ref', 'response_id']:
            g = pd.DataFrame([[header], ['Synthetic Identity']])
            self.assertEqual(safe_preview(g).iloc[1, 0], '[IDENTIFIER WITHHELD]')

    def test_unknown_column_and_model_fail_closed(self):
        for header in ['Surprise column', 'Vehicle', 'Model']:
            self.assertEqual(safe_preview(pd.DataFrame([[header], ['Unlisted Person']])).iloc[1, 0], '[VALUE WITHHELD]')

    def test_unexpected_value_in_allowed_column(self):
        for header in ['Date', 'Department', 'Rating', 'Site']:
            self.assertEqual(safe_preview(pd.DataFrame([[header], ['Unlisted Person']])).iloc[1, 0], '[VALUE WITHHELD]')

    def test_structured_values_preserved(self):
        g = pd.DataFrame([['Date', 'Department', 'Rating', 'Site'], ['02/01/2026', 'Service', 4, 'TSV']])
        self.assertEqual(safe_preview(g).iloc[1].tolist(), ['02/01/2026', 'Service', '4', 'TSV'])

    def test_source_unchanged(self):
        g = pd.DataFrame([['Name', 'Comments'], ['Synthetic Identity', 'Some private text']])
        original = g.copy(deep=True)
        safe_preview(g)
        pd.testing.assert_frame_equal(g, original)

    def test_preamble_withheld_and_scale_note_allowed(self):
        g = pd.DataFrame([['Unlisted Person'], ['Rating: 1 = Excellent, 5 = Poor'], ['Rating'], [1]])
        v = safe_preview(g, header_row=2)
        self.assertEqual(v.iloc[0, 0], '[PREAMBLE WITHHELD]')
        self.assertEqual(v.iloc[1, 0], 'Rating: 1 = Excellent, 5 = Poor')

    def test_invalid_header_rejected(self):
        with self.assertRaises(ValueError):
            safe_preview(pd.DataFrame())


if __name__ == '__main__':
    unittest.main()
