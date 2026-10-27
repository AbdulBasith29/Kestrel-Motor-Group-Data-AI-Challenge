"""Exercise Silver transformation with synthetic feedback, not duplicated rule logic."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import load_config
from bronze import land_sheet
from silver import transform, normalise_rating, parse_date

class SilverTests(unittest.TestCase):
    def setUp(self):
        self.cfg=load_config()
        self.dealers=pd.DataFrame({'dealer_code':['NSW01','VIC09'], 'closed_date':[pd.NaT,pd.NaT]})
    def run_rows(self, rows, filename='Parramatta_test.xlsx', sheet='Log'):
        grid=pd.DataFrame([['Date','Department','Rating','Comments','Customer']]+rows)
        raw=pd.DataFrame(land_sheet(filename,sheet,grid,self.cfg)[0])
        return transform(raw,self.dealers,self.cfg)
    def test_scale_bounds_and_direction(self):
        cases=[('1','rating','Geelong_test.xlsx','2025',5),('10','score (out of 10)','Ringwood.xlsx','Q1',5),
               ('1','score (out of 10)','Ringwood.xlsx','Q1',1),('Bad','rating','Tamworth.xlsx','Log',1),
               ('★★★','stars','X.xlsx','Log',3),('6','rating','X.xlsx','Log',None),
               ('11','score (out of 10)','X.xlsx','Log',None),('nan','rating','X.xlsx','Log',None),
               ('inf','rating','X.xlsx','Log',None),('2.5','rating','X.xlsx','Log',None)]
        for raw,header,file,sheet,expected in cases:
            with self.subTest(raw=raw,header=header):
                self.assertEqual(normalise_rating(SimpleNamespace(rating_raw=raw,rating_header=header,source_file=file,source_sheet=sheet),self.cfg)[0],expected)
    def test_missing_invalid_ratings_and_vague_dates_kept(self):
        f,dq,_=self.run_rows([['early Oct','Service','','Waiting for a callback',''],['02/10/2025','Service','6','Issue remains unresolved','']])
        self.assertTrue(f.in_analysis.all());self.assertTrue(f.rating_1to5.isna().all());self.assertTrue(f.negative.isna().all())
        self.assertTrue(pd.isna(f.iloc[0]['date']))
        self.assertIn('invalid_source_rating',f.iloc[1]['flags'])
    def test_masking_does_not_create_duplicates_and_ids_stable(self):
        rows=[['02/10/2025','Service','1','Jane waited all day without a call','Jane'],
              ['02/10/2025','Service','1','John waited all day without a call','John'],
              ['02/10/2025','Service','1','Jane waited all day without a call','Jane']]
        f,_,decisions=self.run_rows(rows)
        self.assertEqual(f.comment.nunique(),1);self.assertEqual(int(f.in_analysis.sum()),2)
        self.assertEqual(len(decisions),3)
        a=f.set_index('source_row')
        # Reordering an existing Bronze frame preserves IDs for the same source keys.
        grid=pd.DataFrame([['Date','Department','Rating','Comments','Customer']]+rows)
        raw=pd.DataFrame(land_sheet('Parramatta_test.xlsx','Log',grid,self.cfg)[0])
        rev,_,_=transform(raw.iloc[::-1].reset_index(drop=True),self.dealers,self.cfg)
        self.assertEqual(a.response_id.to_dict(),rev.set_index('source_row').response_id.to_dict())
    def test_test_drive_preserved_and_test_row_excluded(self):
        f,_,_=self.run_rows([['02/10/2025','Sales','5','Test drive was excellent',''],['02/10/2025','Sales','5','TEST ignore','']])
        self.assertEqual(f.in_analysis.tolist(),[True,False])
    def test_unknown_labels_and_sales_subtype(self):
        f,_,_=self.run_rows([['02/10/2025','Used Cars','3','Fine',''],['02/10/2025','Unseen team','4','Fine','']])
        self.assertEqual(f.iloc[0].sales_subtype,'Used');self.assertEqual(f.iloc[0].department,'Sales')
        self.assertIn('unknown_department',f.iloc[1]['flags'])
    def test_year_correction_only_reviewed_keys(self):
        filename='Shepparton feedback FINAL - site closed.xlsx'
        f,_,_=self.run_rows([['06/10/2026','Service','3','Fine',''],['07/10/2026','Service','3','Fine','']],filename)
        self.assertEqual(str(f.iloc[0]['date'].date()),'2025-10-06')
        self.assertFalse(f.iloc[1].in_analysis);self.assertIn('quarantined_future_date',f.iloc[1]['flags'])
    def test_source_date_formats(self):
        self.assertEqual(str(parse_date('07/01/2026','liverpool_q3_2026.csv',self.cfg).date()),'2026-07-01')
        self.assertTrue(pd.isna(parse_date('Aug?','IPS.xlsx',self.cfg)))

if __name__=='__main__':unittest.main()
