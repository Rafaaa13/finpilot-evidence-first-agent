import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from finpilot.investment import demo_inputs, analyze_investment
from finpilot.construction import construct

class ConstructionTests(unittest.TestCase):
 def setUp(self): self.r=analyze_investment(**demo_inputs())
 def test_cash_floor_and_caps(self):
  x=construct(self.r,cash_floor=.2,asset_cap=.3,sector_cap=.5,capital=100000)
  self.assertGreaterEqual(x['cash_weight'],.2-1e-10); self.assertTrue(all(h['weight']<=.3+1e-10 for h in x['holdings']))
  self.assertLessEqual(sum(h['weight'] for h in x['holdings']),.8+1e-10)
 def test_manual_weights_and_trade_cost(self):
  ids=self.r['screen']['selected'][:2]
  x=construct(self.r,selected=ids,method='manual',manual={ids[0]:.3,ids[1]:.2},cash_floor=.1,sector_cap=1,capital=100000,current={ids[0]:.1},fee_bps=10)
  self.assertAlmostEqual(x['weights_sum'],.5);self.assertGreater(x['estimated_fees'],0);self.assertEqual(len(x['trades']),2)
 def test_invalid_manual(self):
  ids=self.r['screen']['selected'][:1]
  with self.assertRaises(ValueError): construct(self.r,selected=ids,method='manual',manual={ids[0]:.8},asset_cap=.3)
if __name__=='__main__': unittest.main()
