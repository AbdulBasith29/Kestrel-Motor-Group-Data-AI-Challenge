"""Synthetic role-aware masking and pre-storage tests. No raw dataset values printed."""
from pathlib import Path
import sys,unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from privacy import NameContext,build_name_context
from bronze import land_sheet,header_rows
from common import load_config

class CommentMaskingTests(unittest.TestCase):
    def test_customer_full_and_first_name(self):
        ctx=NameContext()
        text,meta=ctx.mask('Call Jane Example; Jane is waiting.','X',['Jane Example'])
        self.assertEqual(text,'Call [CUSTOMER]; [CUSTOMER] is waiting.')
        self.assertEqual(meta['masked_customer_count'],2)
    def test_staff_dealer_scope(self):
        ctx=NameContext();ctx.staff['A'].add('Zed')
        self.assertEqual(ctx.mask('Zed never called.','A')[0],'[STAFF] never called.')
        self.assertEqual(ctx.mask('Zed never called.','B')[0],'Zed never called.')
    def test_ambiguous_role(self):
        ctx=NameContext();ctx.staff['A'].add('Jane')
        self.assertEqual(ctx.mask('Jane called','A',['Jane'])[0],'[PERSON] called')
    def test_boundaries_case_and_tags(self):
        ctx=NameContext();ctx.staff['A'].add('Ann')
        self.assertEqual(ctx.mask('ANN helped annually [STAFF].','A')[0],'[STAFF] helped annually [STAFF].')
    def test_contacts_and_registrations(self):
        text,meta=NameContext().mask('jane@example.com 0412 345 678 (02) 9000 1234 car ABC123','X')
        self.assertEqual(text,'[EMAIL] [PHONE] [PHONE] car [REGO]')
        self.assertEqual(meta['masked_phone_count'],2)
    def test_unknown_name_status_not_false_assurance(self):
        text,meta=NameContext().mask('Unlisted Person helped','X')
        self.assertIn('Unlisted Person',text)
        self.assertIsNone(meta['has_unmasked_name'])
        self.assertEqual(meta['name_audit_status'],'not_run')
    def test_distinct_raw_comments_keep_distinct_identity(self):
        ctx=NameContext()
        a='Jane liked it';b='John liked it'
        self.assertEqual(ctx.mask(a,'X',['Jane'])[0],ctx.mask(b,'X',['John'])[0])
        self.assertNotEqual(ctx.identity(a),ctx.identity(b))
        self.assertEqual(ctx.identity(a),ctx.identity(a))
    def test_staff_collected_across_dealer_files(self):
        cfg=load_config()
        g1=pd.DataFrame([['Date','Department','Rating','Comments','Staff'],['01/10/2025','Service',1,'Zed never called','']])
        g2=pd.DataFrame([['Date','Department','Rating','Comments','Staff'],['02/10/2025','Sales',5,'Good','Zed']])
        sources=[('Parramatta_A.xlsx','A',g1,''),('Parramatta_B.xlsx','B',g2,'')]
        ctx=build_name_context(sources,cfg,header_rows)
        rows,*_=land_sheet('Parramatta_A.xlsx','A',g1,cfg,ctx)
        self.assertEqual(rows[0]['comment'],'[STAFF] never called')
    def test_only_masked_comment_stored_and_no_identity_columns(self):
        cfg=load_config()
        g=pd.DataFrame([['Date','Department','Rating','Comments','Customer','Staff'],['01/10/2025','Service',1,'Jane says Zed never called','Jane','Zed']])
        before=g.copy(deep=True)
        rows,_,dispositions,_=land_sheet('Parramatta_X.xlsx','X',g,cfg)
        self.assertEqual(rows[0]['comment'],'[CUSTOMER] says [STAFF] never called')
        self.assertFalse(any('Jane' in str(v) or 'Zed' in str(v) for v in rows[0].values()))
        self.assertFalse(any('Jane' in str(v) or 'Zed' in str(v) for d in dispositions for v in d.values()))
        pd.testing.assert_frame_equal(g,before)
    def test_noosa_staff_header(self):
        cfg=load_config()
        g=pd.DataFrame([['Date','Department','Rating','Comments','Card given by'],['01/10/2025','Service',4,'Zed was helpful','Zed']])
        rows,*_=land_sheet('Noosa feedback cards.xlsx','Cards',g,cfg)
        self.assertEqual(rows[0]['comment'],'[STAFF] was helpful')

if __name__=='__main__':unittest.main()
