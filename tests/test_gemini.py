"""Gemini transport, secret handling, accounting and response tests; no real API calls."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import gemini_enrichment as g
from common import ROOT

class GeminiTests(unittest.TestCase):
    def setUp(self):
        self.cfg=g.settings()
        self.output={'sentiment':'negative','themes':[{'theme':'communication_follow_up','polarity':'negative'}],
                     'has_unmasked_name':False,'name_mentions':[],'needs_review':False}
        self.response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(self.output)}]}}],
                       'modelVersion':'test-model','usageMetadata':{'promptTokenCount':1000,'candidatesTokenCount':80,'thoughtsTokenCount':20}}
    def test_gemini_schema_and_minimal_thinking(self):
        body=g.request_body('No callback',self.cfg)
        self.assertEqual(body['generationConfig']['thinkingConfig']['thinkingLevel'],'MINIMAL')
        self.assertEqual(body['generationConfig']['responseFormat']['text']['mimeType'],'APPLICATION_JSON')
        self.assertEqual(json.loads(body['contents'][0]['parts'][0]['text']),{'feedback':'No callback'})
    def test_structured_result_and_thinking_cost(self):
        with patch.object(g,'call',return_value=self.response):r=g.infer('No callback',self.cfg,'secret')
        self.assertEqual(r['status'],'success');self.assertEqual(r['output_tokens_including_thinking'],100)
        self.assertAlmostEqual(r['cost_usd_accounted'],0.00055)
        self.assertNotIn('name_mentions',r);self.assertNotIn('secret',json.dumps(r))
    def test_auth_error_not_retried_or_echoed(self):
        with patch.object(g,'call',side_effect=g.ProviderError('http_403')) as call:
            r=g.infer('No callback',self.cfg,'secret')
        self.assertEqual(call.call_count,1);self.assertEqual(r['error_code'],'http_403')
        self.assertNotIn('No callback',json.dumps(r));self.assertGreater(r['cost_usd_accounted'],0)
    def test_rate_limit_retry_is_bounded_and_accounted(self):
        with patch.object(g,'call',side_effect=[g.ProviderError('http_429'),self.response]),patch.object(g.time,'sleep'):
            r=g.infer('No callback',self.cfg,'secret')
        self.assertEqual(r['attempts'],2);self.assertGreater(r['cost_usd_accounted'],0.00055)
    def test_truncated_response_not_accepted(self):
        response={**self.response,'candidates':[{'finishReason':'MAX_TOKENS'}]}
        with patch.object(g,'call',return_value=response):r=g.infer('No callback',self.cfg,'secret')
        self.assertEqual(r['status'],'error')
    def test_cache_key_changes_with_model_options(self):
        self.assertNotEqual(g.fingerprint('Fine',self.cfg),g.fingerprint('Fine',{**self.cfg,'max_output_tokens':601}))
    def test_secret_only_read_from_known_environment_key(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'synthetic-test-key'}):
            self.assertEqual(g.api_key(),'synthetic-test-key')
    def test_empty_secret_file_is_a_clear_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
            root=Path(directory);(root/'.env').write_text('GEMINI_API_KEY=\n')
            with patch.object(g,'ROOT',root),patch.dict(os.environ,{},clear=True):
                with self.assertRaises(g.ProviderError):g.api_key()
    def test_reservation_covers_maximum_configured_output(self):
        self.assertGreaterEqual(g.reservation('Fine',self.cfg),g.token_cost(0,600,self.cfg)*2)

class GeminiRunTests(unittest.TestCase):
    def test_rolling_run_deduplicates_requests_and_resumes_from_cache(self):
        import pandas as pd
        import duckdb
        cfg=g.settings()
        source=pd.DataFrame([{'response_id':str(i),'dealer_code':'A','department':'Service','rating_1to5':1,
                              'comment':'No callback' if i<2 else 'Waited all day','local_name_screened':False} for i in range(3)])
        result={'status':'success','sentiment':'negative','themes':[], 'has_unmasked_name':False,
                'needs_review':False,'proposed_comment':None,'cost_usd_accounted':0.0001,'latency_seconds':1,
                'model_version':'test','input_tokens':10,'output_tokens_including_thinking':10}
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
            root=Path(directory);(root/'outputs').mkdir();(root/'data').mkdir();db=root/'test.duckdb'
            with patch.object(g,'ROOT',root),patch.object(g,'settings',return_value=cfg),patch.object(g,'api_key',return_value='test'),patch.object(g,'privacy_checked_source',return_value=(source,[],3)),contextlib.redirect_stdout(io.StringIO()):
                with patch.object(g,'infer',return_value=result) as infer:
                    first=g.run(db,workers=2,all_rows=True)
                self.assertEqual(infer.call_count,2)
                with patch.object(g,'infer',side_effect=AssertionError('cache miss')):
                    second=g.run(db,workers=2,all_rows=True)
                self.assertEqual(second['cache_hits'],3);self.assertEqual(first['successful'],3)
                with duckdb.connect(str(db)) as c:
                    self.assertEqual(c.execute('select count(*) from silver.ai_enrichment_gemini').fetchone()[0],3)
                    self.assertAlmostEqual(c.execute('select sum(accounted_usd) from ops.gemini_spend').fetchone()[0],0.0002)
    def test_budget_stops_before_any_api_request(self):
        import pandas as pd
        cfg=g.settings()
        source=pd.DataFrame([{'response_id':'x','dealer_code':'A','department':'Service','rating_1to5':1,
                              'comment':'No callback','local_name_screened':False}])
        with tempfile.TemporaryDirectory(dir=ROOT/'data') as directory:
            root=Path(directory);(root/'outputs').mkdir();(root/'data').mkdir()
            with patch.object(g,'ROOT',root),patch.object(g,'settings',return_value=cfg),patch.object(g,'api_key',return_value='test'),patch.object(g,'privacy_checked_source',return_value=(source,[],1)),patch.object(g,'infer') as infer,contextlib.redirect_stdout(io.StringIO()):
                result=g.run(root/'test.duckdb',budget=0.000001,all_rows=True)
            infer.assert_not_called();self.assertEqual(result['status'],'budget_limit_reached')

if __name__=='__main__':unittest.main()
