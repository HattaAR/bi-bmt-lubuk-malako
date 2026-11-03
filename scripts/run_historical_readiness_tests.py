"""Targeted historical preparation verification; writes strictly to new test DBs."""
import json
import argparse
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--integration-only',action='store_true')
    parser.add_argument('--case',action='append',help='Only these test method names');args=parser.parse_args()
    if os.getenv('BI_BMT_MYSQL_TESTS')!='1':raise ValueError('Explicit test database opt-in required')
    from tests.test_historical_readiness import HistoricalAuditTests,HistoricalReadinessMySQLTests
    from tests.test_historical import HistoricalDateTests,HistoricalMySQLTests
    from tests.test_historical_redesign import HistoricalPresentationTests
    from tests.mysql_support import get_test_connection,test_database_name
    classes=((HistoricalReadinessMySQLTests,HistoricalMySQLTests) if args.integration_only else
        (HistoricalAuditTests,HistoricalDateTests,HistoricalReadinessMySQLTests,HistoricalMySQLTests,HistoricalPresentationTests))
    selected=[(c,[name for name in unittest.defaultTestLoader.getTestCaseNames(c) if not args.case or name in args.case]) for c in classes]
    suite=unittest.TestSuite(c(name) for c,names in selected for name in names)
    if not suite.countTestCases():raise ValueError('No matching tests')
    result=None;cleanup=[]
    try:
        result=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(suite)
    finally:
        # Preserve test history; retire only accounts created by these classes.
        for cls in (HistoricalReadinessMySQLTests,HistoricalMySQLTests):
            name=getattr(cls,'db_name',None)
            if not name:continue
            test_database_name(name)
            try:
                with get_test_connection(database=name) as c:
                    with c.cursor() as q:
                        q.execute('UPDATE app_users SET is_active=0')
                    c.commit()
                cleanup.append(dict(database=name,accounts_retired=True))
            except Exception:
                # A server outage can occur before CREATE DATABASE succeeds.
                # Record incomplete cleanup without emitting driver secrets.
                cleanup.append(dict(database=name,accounts_retired=False))
        evidence=ROOT/'docs/screenshots/historical-readiness';evidence.mkdir(parents=True,exist_ok=True)
        confirmed_preview=getattr(HistoricalReadinessMySQLTests,'last_confirmed_preview',None)
        if confirmed_preview is not None:
            evidence.joinpath('preview-confirmed-synthetic.json').write_text(
                json.dumps(confirmed_preview,default=str,indent=2),encoding='utf-8')
        evidence.joinpath('tests.json').write_text(json.dumps(dict(tests=result.testsRun if result else 0,
            failures=len(result.failures) if result else 1,errors=len(result.errors) if result else 1,
            skipped=len(result.skipped) if result else 0,cleanup=cleanup),indent=2),encoding='utf-8')
    expected=sum(bool(names) for c,names in selected if c in (HistoricalReadinessMySQLTests,HistoricalMySQLTests))
    return 0 if result and result.wasSuccessful() and not result.skipped and len(cleanup)==expected and all(r['accounts_retired'] for r in cleanup) else 1


if __name__=='__main__':raise SystemExit(main())
