"""Historical source grain/audit and operator flow; synthetic sources only."""
from datetime import date
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from openpyxl import Workbook

def workbook(path):
    book=Workbook();sheet=book.active;sheet.title='SQLRESULT'
    sheet.append(['tgl_realisasi','tgl_jatuh_tempo','tgl_akhir_trans','jml_pinjaman','kota_id'])
    same=[date(2020,1,1),date(2020,2,1),date(2020,2,2),Decimal('100.10'),'001']
    sheet.append(same);sheet.append(same)
    sheet.append([date(2020,1,1),date(2020,2,1),date(2020,2,1),Decimal('200.20'),'002'])
    sheet.append([date(2020,1,1),date(2020,2,1),None,-1,'003'])
    book.save(path);book.close();return path

class HistoricalAuditTests(unittest.TestCase):
    def test_bmt_decision_is_bound_to_confirmed_file_and_sheet(self):
        from src.etl.historical import identical_rows_decision
        identity={'sha256':'ddcf0647dc2cead8a19c2878d2bcea9149ee2fc86d6cc3b288d16c364333df28','sheet':'SQLRESULT'}
        decision=identical_rows_decision(identity)
        self.assertEqual(decision['interpretation'],'distinct_financings_equal_values')
        self.assertTrue(decision['retain_all_records'])
        self.assertIsNone(identical_rows_decision(dict(identity,sheet='OTHER')))
        self.assertIsNone(identical_rows_decision(dict(identity,sha256='0'*64)))

    def test_tenor_300_does_not_exclude_a_date_eligible_record(self):
        from src.etl.historical import prepare_historical
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as folder:
            path=workbook(Path(folder)/'tenor-synthetic.xlsx')
            book=load_workbook(path);sheet=book.active;sheet['F1']='bi_jangka_waktu'
            for col,value in enumerate((date(2024,10,17),date(2029,10,17),date(2025,6,25),Decimal('250000000.00'),'SYNTHETIC',300),1):
                sheet.cell(2,col,value)
            book.save(path);book.close();candidate=prepare_historical(path)
        row=next(r for r in candidate.rows if r['source_row_number']==2)
        self.assertEqual(candidate.summary['rows'],4)
        self.assertTrue(row['eligible']);self.assertEqual(row['target_late'],0)
        self.assertEqual(row['contract_duration_days'],1826)
        self.assertEqual(row['date_issues'],[])
        self.assertEqual(row['raw_values']['bi_jangka_waktu']['value'],300)

    def test_same_analytics_but_different_source_columns_are_not_identical(self):
        from src.etl.historical import prepare_historical
        with tempfile.TemporaryDirectory() as folder:
            path=workbook(Path(folder)/'synthetic.xlsx')
            from openpyxl import load_workbook
            book=load_workbook(path);book.active['E3']='different';book.save(path);book.close()
            candidate=prepare_historical(path)
        self.assertEqual(candidate.audit['duplicate_extra_records'],0)
        self.assertEqual(candidate.summary['rows'],4)

    def test_ui_counts_records_not_unique_contracts(self):
        from tests.test_historical_redesign import summary
        from src.ui.executive.historical import analysis_html
        html=analysis_html(summary())
        self.assertIn('record bertanggal valid',html)
        self.assertIn('Record Layak',html)
        self.assertNotIn('kontrak layak',html)
        self.assertIn('Identitas kontrak unik belum tersedia',html)
        from src.services.methodology import DEFINITIONS
        definition=next(item for item in DEFINITIONS if item[0]=='Tingkat keterlambatan historis')
        self.assertIn('Record',definition[1])
        self.assertIn('bukan jumlah kontrak unik',definition[2])

    def test_grain_and_sensitivity_never_drop_candidate_records(self):
        from src.etl.historical import prepare_historical
        with tempfile.TemporaryDirectory() as folder:
            candidate=prepare_historical(workbook(Path(folder)/'synthetic.xlsx'))
        self.assertEqual(candidate.summary['rows'],4)
        self.assertEqual(candidate.audit['duplicate_groups'],[[2,3]])
        self.assertIsNone(candidate.audit['unique_contracts'])
        self.assertEqual(candidate.audit['source_columns'],['tgl_realisasi','tgl_jatuh_tempo','tgl_akhir_trans','jml_pinjaman','kota_id'])
        self.assertEqual(candidate.audit['sensitivity_distinct_rows']['rows'],3)
        self.assertEqual(candidate.audit['sensitivity_distinct_rows']['late'],1)
        self.assertEqual(candidate.summary['late'],2)
        self.assertEqual(candidate.summary['original_principal'],Decimal('400.40'))
        self.assertIn('kota_id',candidate.rows[0]['raw_values'])
        self.assertEqual(candidate.rows[0]['raw_values']['kota_id']['value'],'001')

    def test_dry_run_uses_no_database_and_emits_safe_audit(self):
        from src.etl.load_historical import main
        connection=Mock(side_effect=AssertionError('Dry-run must not connect'))
        with tempfile.TemporaryDirectory() as folder,patch('sys.stdout',new_callable=io.StringIO) as output:
            code=main(['--file',str(workbook(Path(folder)/'synthetic.xlsx')),'--dry-run'],connection_factory=connection)
        self.assertEqual(code,0);connection.assert_not_called()
        data=json.loads(output.getvalue())
        self.assertEqual(data['audit']['duplicate_extra_records'],1)
        self.assertNotIn('raw_values',data)


@unittest.skipUnless(os.getenv('BI_BMT_MYSQL_TESTS')=='1','Dedicated test database required')
class HistoricalReadinessMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_active_kpis import ActiveKPIMySQLTests
        ActiveKPIMySQLTests.setUpClass.__func__(cls)
        from src.etl.load_historical import main
        cls.cli=staticmethod(main)
        with cls.factory() as c:
            with c.cursor() as q:
                q.execute("INSERT INTO app_users(username,display_name) VALUES('synthetic_executive','Synthetic')")
                cls.executive=q.lastrowid
                q.execute("INSERT INTO app_user_roles(user_id,role_code) VALUES(%s,'executive')",(cls.executive,))
            c.commit()
        # Exercise actual CLI migration, including rejection before DDL.
        with patch('sys.stdout',new_callable=io.StringIO):
            if main(['--apply-schema','--admin-id',str(cls.executive)],connection_factory=cls.factory)!=1:
                raise AssertionError('Executive must not apply schema')
            if main(['--apply-schema','--admin-id',str(cls.actor)],connection_factory=cls.factory)!=0:
                raise AssertionError('Synthetic schema migration failed')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)

    def call(self,*args,expected=0):
        with patch('sys.stdout',new_callable=io.StringIO) as output:
            code=self.cli(list(args),connection_factory=self.factory)
        self.assertEqual(code,expected,output.getvalue());return json.loads(output.getvalue())

    def candidate(self,name='synthetic.xlsx',duplicates=False):
        from src.etl.historical import prepare_historical
        import uuid
        path=workbook(Path(self.temp.name)/name)
        from openpyxl import load_workbook
        book=load_workbook(path)
        # A different filename is NOT a different source identity. Give each
        # independent synthetic source distinct bytes, while retaining the pair
        # of identical rows inside a duplicate fixture.
        book.active['F1']='synthetic_batch';batch=uuid.uuid4().hex
        for row in range(2,6):book.active.cell(row,6,batch)
        if not duplicates:book.active['E3']='distinct'
        book.save(path);book.close()
        return prepare_historical(path)

    def load(self,candidate):
        from src.database.historical import load_historical
        return load_historical(candidate,admin_id=self.actor,connection_factory=self.factory)

    def publish(self,dataset,publish=False):
        from src.database.historical import publish_historical
        return publish_historical(dataset,self.actor,publish=publish,connection_factory=self.factory)

    def test_cli_full_flow_and_pointer_separation(self):
        from tests.test_active_kpis import ActiveKPIMySQLTests
        from src.database.historical_analysis import get_historical_summary
        active=ActiveKPIMySQLTests.portfolio(self)
        status=self.call('--status');self.assertTrue(status['fact_table_exists'])
        self.assertEqual(len(status['protection_triggers']),3)
        self.call('--apply-schema','--admin-id',str(self.actor),expected=1)
        candidate=self.candidate()
        args=('--file',str(candidate.source.path),'--load','--admin-id',str(self.actor))
        result=self.call(*args);dataset=result['dataset_version_id']
        self.assertTrue(self.call(*args)['reused'])
        preview=self.call('--preview',str(dataset),'--published-by',str(self.actor))
        self.assertTrue(preview['can_publish']);self.assertEqual(preview['warnings'],2)
        self.assertEqual(preview['summary']['rows'],4)
        publication=self.call('--publish',str(dataset),'--admin-id',str(self.actor))
        self.assertTrue(self.call('--publish',str(dataset),'--admin-id',str(self.actor))['reused'])
        with patch('src.etl.historical.prepare_historical',side_effect=AssertionError('Reader must not read Excel')):
            read=get_historical_summary(connection_factory=self.factory)
        self.assertEqual(read['publication']['publication_id'],publication['publication_id'])
        self.assertEqual((read['contracts'],read['on_time'],read['late']),(3,1,2))
        pointers={r['dataset_kind']:r for r in self.call('--status')['current_publications']}
        self.assertEqual(pointers['active']['publication_id'],active['publication'])
        self.assertEqual(pointers['historical']['publication_id'],publication['publication_id'])
        # A later version is independent; republishing the old one never rewinds.
        other=self.candidate('other.xlsx');other.rows=other.rows[:1]
        second=self.publish(self.load(other)['dataset_version_id'],True)
        self.publish(dataset,True)
        self.assertEqual(get_historical_summary(connection_factory=self.factory)['publication']['publication_id'],second['publication_id'])

    def test_suspected_duplicates_retained_warned_and_publication_held(self):
        candidate=self.candidate(duplicates=True);stored=self.load(candidate);dataset=stored['dataset_version_id']
        self.assertEqual(stored['status'],'ready');self.assertTrue(self.load(candidate)['reused'])
        preview=self.publish(dataset)
        self.assertTrue(preview['technical_ready']);self.assertFalse(preview['can_publish'])
        self.assertEqual(preview['publication_blocker'],'awaiting_bmt_identical_rows')
        self.assertEqual(preview['audit']['duplicate_extra_records'],1)
        self.assertEqual(preview['summary']['rows'],4)
        with self.assertRaises(ValueError):self.publish(dataset,True)
        with self.factory() as c:
            with c.cursor() as q:
                q.execute("SELECT source_row_number FROM validation_findings WHERE dataset_version_id=%s AND rule_code='historical_potential_exact_duplicate' ORDER BY source_row_number",(dataset,))
                self.assertEqual([r['source_row_number'] for r in q.fetchall()],[2,3])
                q.execute('SELECT raw_values FROM fact_pembiayaan_historis WHERE dataset_version_id=%s ORDER BY source_row_number',(dataset,))
                self.assertEqual(len(q.fetchall()),4)

    def test_confirmed_identical_records_keep_lineage_and_allow_preview(self):
        from src.etl.historical import IDENTICAL_ROWS_DECISIONS
        candidate=self.candidate(duplicates=True)
        decision=dict(decision_id='SYNTHETIC-BMT-KEEP-ALL',confirmed_on='2026-11-03',
            interpretation='distinct_financings_equal_values',retain_all_records=True,
            evidence='Synthetic test decision only')
        key=(candidate.source.sha256,candidate.source.sheet)
        with patch.dict(IDENTICAL_ROWS_DECISIONS,{key:decision}):
            stored=self.load(candidate);dataset=stored['dataset_version_id']
            self.assertTrue(self.load(candidate)['reused'])
            preview=self.publish(dataset)
            self.assertTrue(preview['technical_ready']);self.assertTrue(preview['can_publish'])
            self.assertIsNone(preview['publication_blocker'])
            self.assertEqual(preview['audit']['identical_rows_decision'],decision)
            self.assertEqual(preview['audit']['publication_decision'],'confirmed_distinct_records_keep_all')
            self.assertEqual(preview['audit']['duplicate_groups'],[[2,3]])
            self.assertEqual(preview['summary'],candidate.summary)
            with self.factory() as c:
                with c.cursor() as q:
                    q.execute('SELECT historical_fact_id,source_row_number FROM fact_pembiayaan_historis WHERE dataset_version_id=%s ORDER BY source_row_number',(dataset,))
                    facts=q.fetchall()
                    self.assertEqual(len(facts),4);self.assertEqual(len({r['historical_fact_id'] for r in facts}),4)
                    self.assertEqual([r['source_row_number'] for r in facts],[2,3,4,5])
                    q.execute("SELECT source_row_number,message FROM validation_findings WHERE dataset_version_id=%s AND rule_code='historical_identical_values_distinct_records' ORDER BY source_row_number",(dataset,))
                    notes=q.fetchall();self.assertEqual([r['source_row_number'] for r in notes],[2,3])
                    self.assertTrue(all('BMT' in r['message'] and 'menunggu' not in r['message'] for r in notes))
                    q.execute('SELECT COUNT(*) AS n FROM dataset_publications WHERE dataset_version_id=%s',(dataset,))
                    self.assertEqual(q.fetchone()['n'],0) # Preview never publishes.
            published=self.publish(dataset,True)
            self.assertEqual(published['status'],'published')
            self.assertTrue(self.load(candidate)['reused'])
            with self.factory() as c:
                with c.cursor() as q:
                    q.execute('SELECT COUNT(*) AS n FROM fact_pembiayaan_historis WHERE dataset_version_id=%s',(dataset,))
                    self.assertEqual(q.fetchone()['n'],4)

    def test_confirmed_3709_records_reconcile_without_deduplication(self):
        from src.etl.historical import IDENTICAL_ROWS_DECISIONS,prepare_historical
        path=Path(self.temp.name)/'large-synthetic.xlsx'
        book=Workbook();sheet=book.active;sheet.title='SQLRESULT'
        sheet.append(['tgl_realisasi','tgl_jatuh_tempo','tgl_akhir_trans','jml_pinjaman','kota_id'])
        base=[[date(2020,1,1),date(2020,2,1),date(2020,2,2) if i%2 else date(2020,2,1),
               Decimal('100.10'),f'SYNTHETIC-{i:05d}'] for i in range(3664)]
        for row in base:sheet.append(row)
        for i in range(44):sheet.append(base[i])
        sheet.append(base[0]);book.save(path);book.close()
        candidate=prepare_historical(path)
        decision=dict(decision_id='SYNTHETIC-3709-KEEP-ALL',confirmed_on='2026-11-03',
            interpretation='distinct_financings_equal_values',retain_all_records=True,evidence='Synthetic only')
        with patch.dict(IDENTICAL_ROWS_DECISIONS,{(candidate.source.sha256,candidate.source.sheet):decision}):
            stored=self.load(candidate);dataset=stored['dataset_version_id']
            repeated=self.load(candidate)
            self.assertTrue(repeated['reused']);self.assertEqual(repeated['dataset_version_id'],dataset)
            preview=self.publish(dataset)
            self.assertTrue(preview['can_publish']);self.assertEqual(preview['reconciliation'],'passed')
            self.assertEqual(preview['summary'],candidate.summary)
            self.assertEqual(preview['summary']['rows'],3709)
            self.assertEqual(preview['summary']['original_principal'],Decimal('371270.90'))
            self.assertEqual(preview['audit']['duplicate_group_count'],44)
            self.assertEqual(preview['audit']['duplicate_extra_records'],45)
            self.assertEqual(preview['audit']['identical_records'],89)
            self.assertEqual(preview['warnings'],89)
            with self.factory() as c:
                with c.cursor() as q:
                    q.execute('SELECT COUNT(*) AS n,COUNT(DISTINCT source_row_number) AS source_lines FROM fact_pembiayaan_historis WHERE dataset_version_id=%s',(dataset,))
                    self.assertEqual(q.fetchone(),dict(n=3709,source_lines=3709))
            type(self).last_confirmed_preview=preview

    def test_admin_guard_load_preview_publish_and_inactive(self):
        from src.database.historical import load_historical,publish_historical
        candidate=self.candidate();dataset=self.load(candidate)['dataset_version_id']
        for actor in (None,self.executive):
            with self.assertRaises(ValueError):load_historical(candidate,admin_id=actor,connection_factory=self.factory)
            for action in (False,True):
                with self.assertRaises(ValueError):publish_historical(dataset,actor,publish=action,connection_factory=self.factory)
        with self.factory() as c:
            with c.cursor() as q:q.execute('UPDATE app_users SET is_active=0 WHERE user_id=%s',(self.actor,))
            c.commit()
        try:
            with self.assertRaises(ValueError):self.publish(dataset,True)
        finally:
            with self.factory() as c:
                with c.cursor() as q:q.execute('UPDATE app_users SET is_active=1 WHERE user_id=%s',(self.actor,))
                c.commit()

    def test_manifest_detects_same_totals_tampering_or_missing_warning(self):
        for kind in ('raw','warning','blocking','audit','decision'):
            candidate=self.candidate(kind+'.xlsx');dataset=self.load(candidate)['dataset_version_id']
            with self.factory() as c:
                with c.cursor() as q:
                    if kind=='raw':q.execute("UPDATE fact_pembiayaan_historis SET raw_values='{}' WHERE dataset_version_id=%s AND source_row_number=2",(dataset,))
                    elif kind=='warning':q.execute('DELETE FROM validation_findings WHERE dataset_version_id=%s',(dataset,))
                    elif kind=='blocking':q.execute("UPDATE validation_findings SET severity='blocking' WHERE dataset_version_id=%s",(dataset,))
                    else:
                        q.execute('SELECT scope_description FROM dataset_versions WHERE dataset_version_id=%s',(dataset,))
                        metadata=json.loads(q.fetchone()['scope_description'])
                        if kind=='audit':metadata['audit']['duplicate_extra_records']=999
                        else:metadata['audit']['identical_rows_decision']={'retain_all_records':True}
                        q.execute('UPDATE dataset_versions SET scope_description=%s WHERE dataset_version_id=%s',(json.dumps(metadata),dataset))
                c.commit()
            with self.assertRaises(ValueError):self.publish(dataset)
            with self.assertRaises(ValueError):self.load(candidate)

    def test_incomplete_migration_rejects_writes_and_can_be_inspected(self):
        candidate=self.candidate()
        with self.factory() as c:
            with c.cursor() as q:
                q.execute('SHOW CREATE TRIGGER protect_historical_insert');definition=q.fetchone()['SQL Original Statement']
                q.execute('DROP TRIGGER protect_historical_insert')
        try:
            self.assertEqual(len(self.call('--status')['protection_triggers']),2)
            with self.assertRaises(ValueError):self.load(candidate)
        finally:
            with self.factory() as c:
                with c.cursor() as q:q.execute(definition)

    def test_all_fact_mutations_rejected_after_publication(self):
        import pymysql
        candidate=self.candidate();dataset=self.load(candidate)['dataset_version_id'];self.publish(dataset,True)
        with self.factory() as c:
            with c.cursor() as q:
                queries=[('DELETE FROM fact_pembiayaan_historis WHERE dataset_version_id=%s',(dataset,)),
                    ("UPDATE fact_pembiayaan_historis SET raw_values='{}' WHERE dataset_version_id=%s",(dataset,)),
                    ('''INSERT INTO fact_pembiayaan_historis(dataset_version_id,source_file_id,source_sheet,source_row_number,
                        eligible,date_issues,raw_values) SELECT dataset_version_id,source_file_id,source_sheet,99,0,'[]','{}'
                        FROM fact_pembiayaan_historis WHERE dataset_version_id=%s LIMIT 1''',(dataset,))]
                for sql,args in queries:
                    with self.assertRaises(pymysql.MySQLError):q.execute(sql,args)
                    c.rollback()
