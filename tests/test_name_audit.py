"""Literal-name masking tests with synthetic feedback; model offsets are forbidden."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from name_audit import validate_and_mask

class NameAuditTests(unittest.TestCase):
    def result(self,*names):return {'has_unmasked_name':bool(names),'mentions':[{'text':name,'role':'STAFF'} for name in names]}
    def test_clear(self):self.assertEqual(validate_and_mask('Good service',self.result()),'Good service')
    def test_nervous_word_preserved(self):
        self.assertEqual(validate_and_mask('I was nervous but Lena sent updates.',self.result('Lena')),'I was nervous but [STAFF] sent updates.')
    def test_monday_preserved(self):
        self.assertEqual(validate_and_mask('Called on Monday; Evan never called back.',self.result('Evan')),'Called on Monday; [STAFF] never called back.')
    def test_workshop_preserved(self):
        self.assertEqual(validate_and_mask('No slot at the workshop. Evan apologised.',self.result('Evan')),'No slot at the workshop. [STAFF] apologised.')
    def test_help_was_preserved(self):
        self.assertEqual(validate_and_mask('The help was genuine. evan was great.',self.result('evan')),'The help was genuine. [STAFF] was great.')
    def test_short_names_replaced_without_damaging_neighbours(self):
        self.assertEqual(validate_and_mask('Evan was a gentleman. Evan explained everything.',self.result('Evan')),'[STAFF] was a gentleman. [STAFF] explained everything.')
    def test_unknown_or_partial_substrings_rejected(self):
        for text,name in [('Annually','Ann'),('Jane called','Jan'),('Fine','Jane')]:
            with self.assertRaises(ValueError):validate_and_mask(text,self.result(name))
    def test_exact_case_required(self):
        with self.assertRaises(ValueError):validate_and_mask('jane called',self.result('Jane'))
    def test_mask_tags_protected(self):
        with self.assertRaises(ValueError):validate_and_mask('[STAFF] called',self.result('STAFF'))
    def test_flag_mismatch_rejected(self):
        with self.assertRaises(ValueError):validate_and_mask('Fine',{'has_unmasked_name':True,'mentions':[]})
    def test_legacy_offsets_rejected(self):
        with self.assertRaises(ValueError):validate_and_mask('Jane called',{'has_unmasked_name':True,'spans':[{'start':0,'end':4,'role':'STAFF'}]})
    def test_overlapping_names_rejected(self):
        with self.assertRaises(ValueError):validate_and_mask('Jane Doe called',self.result('Jane Doe','Doe'))

if __name__=='__main__':unittest.main()
