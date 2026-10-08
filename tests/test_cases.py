import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from finpilot.cases import historical_case_catalog, analyze_all_reference_cases, analyze_reference_case

class HistoricalCaseTests(unittest.TestCase):
    def test_catalog_has_public_snapshot_cases(self):
        data=historical_case_catalog()
        self.assertEqual(data['data_status'],'public_reference_snapshot')
        self.assertGreaterEqual(len(data['cases']),3)
        self.assertTrue(all(c['source_urls'] for c in data['cases']))
    def test_covid_case_math_is_descriptive(self):
        data=historical_case_catalog()
        case=next(c for c in data['cases'] if c['case_id']=='sp500_covid_2020')
        result=analyze_reference_case(case)
        self.assertAlmostEqual(result['trough_value']/result['start_value']-1,result['peak_to_trough_change'])
        self.assertLess(result['peak_to_trough_change'],0)
        self.assertIn('not a complete series',result['caveat'])
    def test_all_cases_jsonable(self):
        results=analyze_all_reference_cases()
        self.assertEqual(len(results),3)
        self.assertTrue(all(r['status']=='valid' for r in results))

    def test_official_financial_casebook_has_derived_metrics_and_sources(self):
        from finpilot.cases import financial_casebook, all_financial_cases
        catalog=financial_casebook(); results=all_financial_cases()
        self.assertEqual(catalog['data_status'],'official_public_snapshot')
        self.assertEqual(len(results),4)
        apple=next(x for x in results if x['case_id']=='apple_fy2024_profit_quality')
        self.assertAlmostEqual(apple['derived_metrics']['net_margin'],93736/391035)
        self.assertTrue(all(x['source_urls'] for x in results))

    def test_real_case_what_if_tools_are_explicit(self):
        from finpilot.cases import endpoint_exposure, futures_pnl
        self.assertAlmostEqual(endpoint_exposure(3386.15,2237.40,.6,100000)['portfolio_change'], .6*(2237.40/3386.15-1))
        self.assertLess(futures_pnl(20,-37.63,1,1000,10000)['pnl'],0)

if __name__=='__main__':unittest.main()
