import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from finpilot.advisor import enhancement_preview, enhance
from finpilot.investment import analyze_investment, demo_inputs

class AdvisorTests(unittest.TestCase):
    def setUp(self): self.result=analyze_investment(**demo_inputs())
    def test_preview_is_local_and_contains_no_raw_csv(self):
        p=enhancement_preview(self.result,'为什么被排除？')
        self.assertEqual(p['data_label'],'合成示例，非真实证券')
        self.assertNotIn('DEMO01,示例云服务',str(p))
        self.assertGreaterEqual(len(p['findings']),2)
    def test_offline_enhancement_returns_diligence_checklist(self):
        r=enhance(self.result,'请帮我准备人工核查问题')
        self.assertEqual(r['status'],'offline');self.assertEqual(r['model_calls'],0)
        self.assertGreaterEqual(len(r['questions']),1)

if __name__=='__main__':unittest.main()
