import sys, unittest, json, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from finpilot.investment import demo_inputs, analyze_investment, _csv, STOCK_FIELDS

class InvestmentTests(unittest.TestCase):
    def setUp(self): self.x=demo_inputs()
    def test_demo_screen_excludes_bad_and_late_rows(self):
        r=analyze_investment(**self.x)
        self.assertEqual(r['data_kind'],'synthetic'); self.assertIn('DEMO01',r['screen']['selected'])
        excluded={x['symbol']:x['reasons'] for x in r['screen']['excluded']}
        self.assertIn('DEMO04',excluded); self.assertIn('营业利润率或自由现金流率不为正',excluded['DEMO04'])
        self.assertIn('DEMO08',excluded); self.assertIn('披露日期晚于研究日',excluded['DEMO08'])
    def test_hand_pe_growth_and_weight_sum(self):
        r=analyze_investment(**self.x,method='equal',weight_cap=.3)
        row=next(x for x in r['screen']['rows'] if x['symbol']=='DEMO01')
        self.assertAlmostEqual(row['pe'],20.0); self.assertAlmostEqual(row['components']['growth'],60.0)
        self.assertAlmostEqual(r['portfolio']['weights_sum']+r['portfolio']['cash_weight'],1.0)
        self.assertTrue(all(h['weight']<=.3+1e-12 for h in r['portfolio']['holdings']))
    def test_risk_has_three_scenarios(self):
        r=analyze_investment(**self.x)
        self.assertEqual(r['risk']['status'],'valid'); self.assertEqual(len(r['risk']['scenarios']),3)
        self.assertTrue(all(s['portfolio_loss'] is not None for s in r['risk']['scenarios']))
    def test_input_errors_are_actionable(self):
        bad=self.x['stocks_csv'].replace('DEMO01,','DEMO01,',1).replace('2025-09-02','2025-12-31',1)
        with self.assertRaisesRegex(ValueError,'期末不能晚于披露日'):
            analyze_investment(bad,self.x['prices_csv'])
        with self.assertRaisesRegex(ValueError,'重复'):
            analyze_investment(self.x['stocks_csv'],self.x['prices_csv']+'\n'+self.x['prices_csv'].splitlines()[1])
    def test_content_is_json_serializable(self):
        r=analyze_investment(**self.x)
        json.dumps(r,ensure_ascii=False,allow_nan=False)
        self.assertTrue(r['content_hash'])

    def test_valuation_sensitivity_is_explicit_not_forecast(self):
        r=analyze_investment(**self.x)
        item=next(x for x in r['valuation_sensitivity'] if x['symbol']=='DEMO01')
        self.assertEqual(item['status'],'descriptive')
        self.assertEqual(item['points'][0]['multiple'],10)
        self.assertIn('not a target price',item['caveat'])

if __name__=='__main__':unittest.main()
