import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from finpilot.market_cases import load_sp500_snapshot, market_case_windows
class MarketCaseTests(unittest.TestCase):
 def test_snapshot_is_public_labeled_and_complete(self):
  x=load_sp500_snapshot();self.assertEqual(x['data_kind'],'public_snapshot');self.assertEqual(len(x['rows']),72);self.assertFalse(x['verified']);json.dumps(x,allow_nan=False)
 def test_windows_have_real_monthly_observations(self):
  cases=market_case_windows();self.assertEqual(len(cases),3);self.assertTrue(all(c['observations']>=12 for c in cases));self.assertLess(next(c for c in cases if c['case_id']=='rate_shock_2022')['return'],0)
if __name__=='__main__':unittest.main()
