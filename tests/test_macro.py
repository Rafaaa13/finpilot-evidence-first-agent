import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from finpilot.macro import load_public_macro, macro_latest
class MacroTests(unittest.TestCase):
 def test_public_macro_catalog_is_local_and_labeled(self):
  x=load_public_macro();self.assertEqual(x['data_status'],'public_snapshot');self.assertEqual(len(x['datasets']),3);self.assertTrue(all(not d['verified'] for d in x['datasets']))
  self.assertEqual(len(macro_latest('United States')),3);json.dumps(x,allow_nan=False)
if __name__=='__main__':unittest.main()
