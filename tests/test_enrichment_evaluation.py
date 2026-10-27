"""Synthetic evaluation tests; no generated labels presented as human review."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,MagicMock
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import evaluate_enrichment as e
from common import ROOT

class EvaluationTests(unittest.TestCase):
    def run_fixture(self,labels,predictions):
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
            root=Path(directory);(root/'outputs').mkdir();path=root/'labels.csv'
            pd.DataFrame(labels).to_csv(path,index=False)
            connection=MagicMock();connection.__enter__.return_value.execute.return_value.df.return_value=pd.DataFrame(predictions)
            with patch.object(e,'ROOT',root),patch.object(e.duckdb,'connect',return_value=connection),contextlib.redirect_stdout(io.StringIO()):
                return e.evaluate('unused.duckdb',path)
    def test_unlabelled_reports_pending(self):
        result=self.run_fixture([{'response_id':'x','masked_comment':'Fine','human_sentiment':'',
                                 'human_themes':'','human_has_unmasked_name':''}],[])
        self.assertEqual(result['status'],'awaiting_human_labels');self.assertIsNone(result['sentiment_accuracy'])
    def test_metrics_include_name_misses_and_theme_disagreement(self):
        text='Jane never called'
        labels=[{'response_id':'x','masked_comment':text,'human_sentiment':'negative',
                 'human_themes':'communication_follow_up','human_has_unmasked_name':'true'}]
        predicted=[{'response_id':'x','content_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'sentiment':'negative','themes_json':json.dumps([{'theme':'staff_service','polarity':'negative'}]),
                    'has_unmasked_name':False,'status':'success'}]
        result=self.run_fixture(labels,predicted)
        self.assertEqual(result['sentiment_accuracy'],1);self.assertEqual(result['theme_micro_f1'],0)
        self.assertEqual(result['residual_name_false_negatives'],1)
        self.assertEqual(result['all_reviewed_fields_exact_count'],0)
    def test_all_reviewed_fields_must_match(self):
        text='Helpful team'
        labels=[{'response_id':'x','masked_comment':text,'human_sentiment':'positive',
                 'human_themes':'staff_service','human_has_unmasked_name':'false'}]
        predicted=[{'response_id':'x','content_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'sentiment':'positive','themes_json':json.dumps([{'theme':'staff_service','polarity':'positive'}]),
                    'has_unmasked_name':False,'status':'success'}]
        result=self.run_fixture(labels,predicted)
        self.assertEqual(result['all_reviewed_fields_exact_count'],1)
        self.assertEqual(result['all_reviewed_fields_exact_match_rate'],1)
    def test_partial_theme_credit_reports_extra_and_missed_themes(self):
        text='Delayed and no callback'
        labels=[{'response_id':'x','masked_comment':text,'human_sentiment':'negative',
                 'human_themes':'communication_follow_up|waiting_time_scheduling','human_has_unmasked_name':'false'}]
        predicted=[{'response_id':'x','content_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'sentiment':'negative','themes_json':json.dumps([{'theme':'communication_follow_up','polarity':'negative'},
                    {'theme':'staff_service','polarity':'negative'}]),'has_unmasked_name':False,'status':'success'}]
        result=self.run_fixture(labels,predicted)
        self.assertEqual(result['theme_any_match_rate_on_themed_comments'],1)
        self.assertEqual(result['theme_exact_match'],0)
        self.assertEqual(result['theme_micro_f1'],0.5)
        self.assertEqual(result['per_theme']['communication_follow_up']['hits'],1)
        self.assertEqual(result['per_theme']['waiting_time_scheduling']['misses'],1)
        self.assertEqual(result['per_theme']['staff_service']['extra_predictions'],1)
    def test_no_theme_rows_do_not_inflate_any_match_metric(self):
        text='...'
        labels=[{'response_id':'x','masked_comment':text,'human_sentiment':'unclear',
                 'human_themes':'none','human_has_unmasked_name':'false'}]
        predicted=[{'response_id':'x','content_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'sentiment':'unclear','themes_json':'[]','has_unmasked_name':False,'status':'success'}]
        result=self.run_fixture(labels,predicted)
        self.assertIsNone(result['theme_any_match_rate_on_themed_comments'])
        self.assertEqual(result['theme_exact_match'],1)
    def test_unmapped_themes_do_not_discard_sentiment_or_name_labels(self):
        text='Process was smooth'
        labels=[{'response_id':'x','masked_comment':text,'human_sentiment':'positive',
                 'human_themes':'','human_has_unmasked_name':'false'}]
        predicted=[{'response_id':'x','content_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'sentiment':'positive','themes_json':'[]','has_unmasked_name':False,'status':'success'}]
        result=self.run_fixture(labels,predicted)
        self.assertEqual(result['sentiment_correct_count'],1)
        self.assertEqual(result['human_sentiment_labelled_rows'],1)
        self.assertEqual(result['human_theme_labelled_rows'],0)
        self.assertEqual(result['name_flag_correct_count'],1)
        self.assertIsNone(result['all_reviewed_fields_exact_match_rate'])
    def test_changed_text_rejected(self):
        labels=[{'response_id':'x','masked_comment':'Fine','human_sentiment':'positive',
                 'human_themes':'none','human_has_unmasked_name':'false'}]
        predicted=[{'response_id':'x','content_sha256':'outdated','sentiment':'positive',
                    'themes_json':'[]','has_unmasked_name':False,'status':'success'}]
        with self.assertRaises(ValueError):self.run_fixture(labels,predicted)

if __name__=='__main__':unittest.main()
