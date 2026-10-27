"""Enrichment contracts and selection tests use synthetic comments only."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import enrichment as e

class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.cfg=e.load_settings()
        self.clear={'sentiment':'negative','themes':[{'theme':'communication_follow_up','polarity':'negative'}],
                    'has_unmasked_name':False,'name_mentions':[],'needs_review':False}
    def test_clear_contract(self):
        self.assertIsNone(e.validate_result('No callback',self.clear,self.cfg)['proposed_comment'])
    def test_remaining_name_proposal(self):
        r={**self.clear,'has_unmasked_name':True,'name_mentions':[{'text':'Jane','role':'STAFF'}]}
        result=e.validate_result('Jane never called',r,self.cfg)
        self.assertEqual(result['proposed_comment'],'[STAFF] never called');self.assertTrue(result['needs_review'])
    def test_reject_invented_or_duplicate_themes(self):
        for themes in [[{'theme':'made_up','polarity':'negative'}],self.clear['themes']*2]:
            with self.assertRaises(ValueError):e.validate_result('No callback',{**self.clear,'themes':themes},self.cfg)
    def test_reject_name_flag_disagreement_and_existing_tags(self):
        for r in [{**self.clear,'has_unmasked_name':True},
                  {**self.clear,'has_unmasked_name':True,'name_mentions':[{'text':'STAFF','role':'STAFF'}]}]:
            with self.assertRaises(ValueError):e.validate_result('[STAFF] never called',r,self.cfg)
    def test_unclear_abstains(self):
        r={**self.clear,'sentiment':'unclear','themes':[]}
        self.assertTrue(e.validate_result('...',r,self.cfg)['needs_review'])
    def test_cache_invalidates_on_model_prompt_text_or_settings(self):
        key=e.fingerprint('Fine',self.cfg,'digest1','1')
        for text,cfg,digest in [('Other',self.cfg,'digest1'),('Fine',self.cfg,'digest2'),
                                ('Fine',{**self.cfg,'max_output_tokens':601},'digest1')]:
            self.assertNotEqual(key,e.fingerprint(text,cfg,digest,'1'))
    def test_no_rating_or_dealer_is_sent_to_model(self):
        p=e.payload('Fine',self.cfg)
        self.assertFalse(p['think']);self.assertFalse(p['stream'])
        self.assertEqual(p['messages'][1]['content'],'{"feedback": "Fine"}')
    def test_bad_model_contract_is_error_after_bounded_attempts(self):
        with patch.object(e,'request',return_value={'done':True,'message':{'content':'{"bad":1}'}}) as call:
            result=e.infer('Fine',self.cfg)
        self.assertEqual(result['status'],'error');self.assertEqual(call.call_count,self.cfg['max_attempts'])
        self.assertNotIn('comment',result)
    def test_long_comment_is_not_silently_truncated(self):
        with patch.object(e,'request') as call:
            result=e.infer('a'*(self.cfg['max_comment_characters']+1),self.cfg)
        self.assertEqual(result['error_code'],'comment_too_long');call.assert_not_called()
    def test_local_model_only(self):
        with patch.object(e,'request',side_effect=[{'models':[{'name':'qwen3:4b','digest':'x'}]}, {'remote_host':'remote'}]):
            with self.assertRaises(ValueError):e.local_model(self.cfg)
    def test_deterministic_sample_spreads_rating_bands(self):
        frame=pd.DataFrame([{'response_id':str(i),'dealer_code':str(i%4),'rating_1to5':None if i<5 else (i%5)+1} for i in range(50)])
        a=e.choose_sample(frame,20,'seed');b=e.choose_sample(frame.iloc[::-1],20,'seed')
        self.assertEqual(a.response_id.tolist(),b.response_id.tolist())
        self.assertEqual(len(a),20);self.assertEqual(int(a.band.eq('missing').sum()),4)
        self.assertFalse(a.response_id.duplicated().any())

if __name__=='__main__':unittest.main()
