import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import name_repair as n

class RepairTests(unittest.TestCase):
    def test_exact_names_used_without_model_offsets(self):
        cfg=n.g.settings()
        model={'has_unmasked_name':True,'mentions':[{'text':'Lena','role':'STAFF'}]}
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(model)}]}}],
                  'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20}}
        with patch.object(n.g,'call',return_value=response):r=n.infer('I was nervous; Lena helped.',cfg,'synthetic-key')
        self.assertEqual(r['proposed_comment'],'I was nervous; [STAFF] helped.')
        self.assertNotIn('mentions',r)
    def test_bad_literal_produces_no_proposal(self):
        cfg=n.g.settings()
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'has_unmasked_name':True,'mentions':[{'text':'Invented','role':'STAFF'}]})}]}}]}
        with patch.object(n.g,'call',return_value=response):r=n.infer('Fine service',cfg,'synthetic-key')
        self.assertIsNone(r['proposed_comment']);self.assertEqual(r['proposal_status'],'repair_error_pending_review')

if __name__=='__main__':unittest.main()
