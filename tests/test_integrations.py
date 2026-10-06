"""Offline protocol and bounded-agent regression tests. No third-party servers."""
import unittest
import sys
import json
import io
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from finpilot.integrations import McpStdioClient, LlmClient, IntegrationError, normalize_mcp_records
from finpilot.data import FixtureProvider, validate_ticker, validate_as_of
from finpilot.runtime import run_agent
from finpilot.pipeline import run_fixture


class MockModel:
    def __init__(self, outputs): self.outputs=list(outputs); self.calls=[]
    def __call__(self, request, timeout=30):
        self.calls.append(json.loads(request.data))
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(self.outputs.pop(0))}}], 'usage':{'prompt_tokens':123,'completion_tokens':22}}).encode())


class IntegrationTests(unittest.TestCase):
    def test_mcp_initialize_discover_and_allowlist(self):
        script='''import sys,json
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r: continue
 if r['method']=='tools/list': result={'tools':[{'name':'read_facts'}]}
 elif r['method']=='tools/call': result={'content':[{'type':'text','text':'safe fixture'}]}
 else: result={'protocolVersion':'2024-11-05','capabilities':{},'serverInfo':{'name':'fake','version':'0'}}
 print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)
'''
        with McpStdioClient([sys.executable,'-u','-c',script],allowed_tools=['read_facts']) as client:
            self.assertEqual(client.list_tools()[0].name,'read_facts')
            self.assertIn('content',client.call_read_only('read_facts',{}))
            with self.assertRaises(IntegrationError): client.call_read_only('write_account',{})
    def test_mcp_timeout_is_real(self):
        start=time.monotonic()
        with self.assertRaises(IntegrationError):
            with McpStdioClient([sys.executable,'-u','-c','import time;time.sleep(8)'],timeout=.15): pass
        self.assertLess(time.monotonic()-start,3)
    def test_mcp_wrong_id(self):
        script="import sys,json;sys.stdin.readline();print(json.dumps({'id':99,'result':{}}),flush=True)"
        with self.assertRaises(IntegrationError):
            with McpStdioClient([sys.executable,'-u','-c',script]): pass
    def test_llm_unknown_evidence_rejected(self):
        mock=MockModel([{'claims':[{'text':'x','evidence_ids':['invented']}]}])
        client=LlmClient('http://127.0.0.1:11434/v1',opener=mock)
        with self.assertRaises(IntegrationError): client.draft({}, {'allowed'})
    def test_llm_empty_citation_rejected(self):
        mock=MockModel([{'claims':[{'text':'x','evidence_ids':[]}]}])
        with self.assertRaises(IntegrationError): LlmClient('https://example.test/v1',opener=mock).draft({}, {'allowed'})
    def test_nonlocal_http_endpoint_rejected(self):
        with self.assertRaises(IntegrationError): LlmClient('http://example.test/v1')
    def test_model_really_selects_then_executes_tools(self):
        mock=MockModel([{'tools':['credit','bond']},{'finding_ids':['bond-dv01']}])
        r=run_agent(run_fixture(output_dir=None), '风险', LlmClient('http://127.0.0.1:11434/v1',opener=mock))
        self.assertEqual(r['model_calls'],2);self.assertEqual(len(mock.calls),2)
        self.assertEqual([x['claim_id'] for x in r['findings']],['bond-dv01'])
        self.assertIn('977.8345',r['findings'][0]['text'])
        self.assertEqual(r['engine'],'live_model_planner')
    def test_forbidden_plan_falls_back_and_logs_review(self):
        mock=MockModel([{'tools':['execute_shell']}])
        r=run_agent(run_fixture(output_dir=None), '信用',LlmClient('http://127.0.0.1:11434/v1',opener=mock))
        self.assertEqual(r['status'],'review');self.assertEqual(r['engine'],'offline_rule_router')
        self.assertEqual(r['findings'][0]['claim_id'],'credit-el')
    def test_model_cannot_inject_new_finding(self):
        mock=MockModel([{'tools':['credit']},{'finding_ids':['fake-profit']}])
        r=run_agent(run_fixture(output_dir=None),'信用',LlmClient('http://127.0.0.1:11434/v1',opener=mock))
        self.assertEqual(r['status'],'review');self.assertEqual(r['findings'][0]['claim_id'],'credit-el')
    def test_normalization_rejects_unknown_unit(self):
        with self.assertRaises(ValueError): normalize_mcp_records([{'metric':'close','value':2,'unit':'??','effective_at':'2024-01-01','source_locator':'https://example.test'}],'DEMO','2025-01-01','fixture')


class DataTests(unittest.TestCase):
    def test_past_is_stable(self):
        p=FixtureProvider();old=p.load('DEMO','2023-12-31');new=p.load('DEMO','2025-12-31')
        self.assertTrue({o.raw_ref for o in old.observations}<={o.raw_ref for o in new.observations})
    def test_real_symbol_cannot_rename_synthetic_data(self):
        r=FixtureProvider().load('AAPL','2025-12-31')
        self.assertEqual({o.entity_id for o in r.observations},{'DEMO'})
    def test_bad_inputs(self):
        for v in ['../AAPL','', '<svg>', 'AAPL;echo']:
            with self.assertRaises(ValueError):validate_ticker(v)
        with self.assertRaises(ValueError):validate_as_of('2025-02-30')


if __name__=='__main__':unittest.main()
