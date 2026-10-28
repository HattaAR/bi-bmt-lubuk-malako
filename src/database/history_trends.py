"""Read-only active-report inventory. Publication events are never position trends."""
from src.database.connection import get_connection
from src.database.active_portfolio import current_active_publication


def assess_readiness(reports):
    confirmed=[r for r in reports if r['position_date'] is not None and r['position_date_status']=='confirmed']
    positions={r['position_date'] for r in confirmed}
    identities=[tuple(sorted(set(r['source_hashes']))) for r in confirmed]
    versions={(r['schema_version'],r['mapping_version'],r['validation_rule_version']) for r in confirmed}
    if not reports:reason='no_publication'
    elif len(positions)<2:reason='insufficient_confirmed_positions'
    elif any(not k for k in identities):reason='source_identity_missing'
    elif len(set(identities))!=len(identities):reason='repeated_source'
    elif len(versions)>1:reason='definitions_unverified'
    else:reason='scope_unverified'
    # Existing metadata has no approved business coverage/comparability contract.
    # Matching row counts or schema IDs cannot establish it. No chart is enabled.
    return dict(available=False,reason=reason,published_reports=len(reports),distinct_confirmed_positions=len(positions),
                unknown_positions=len(reports)-len(confirmed),scope_verified=False,definition_versions_consistent=len(versions)<=1)


def get_history_trends(*,connection_factory=get_connection):
    connection=connection_factory()
    try:
        connection.rollback()
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');cursor.execute('START TRANSACTION READ ONLY')
            current=current_active_publication(cursor)
            cursor.execute('''SELECT d.dataset_version_id,d.status,d.created_at,d.position_date,d.position_date_status,
                d.export_date,d.export_period_text,d.schema_version,d.mapping_version,d.validation_rule_version,
                p.publication_id,p.published_at,
                (SELECT COUNT(*) FROM fact_pembiayaan_aktif f WHERE f.dataset_version_id=d.dataset_version_id) AS contracts
                FROM dataset_versions d LEFT JOIN dataset_publications p USING(dataset_version_id)
                WHERE d.dataset_kind=%s ORDER BY d.created_at DESC,d.dataset_version_id DESC''',('active',))
            inventory=list(cursor.fetchall())
            by_id={r['dataset_version_id']:r for r in inventory}
            for row in inventory:row.update(sources=[],source_hashes=[])
            if inventory:
                placeholders=','.join(['%s']*len(inventory))
                cursor.execute('''SELECT ds.dataset_version_id,s.original_filename,s.uploaded_at,s.file_sha256,ds.sheet_name
                    FROM dataset_sources ds JOIN source_files s USING(source_file_id)
                    WHERE ds.dataset_version_id IN ('''+placeholders+''') AND ds.source_role=%s
                    ORDER BY ds.dataset_version_id,s.source_file_id,ds.sheet_name''',(*by_id,'active_primary'))
                for source in cursor.fetchall():
                    row=by_id[source['dataset_version_id']]
                    row['sources'].append(dict(filename=source['original_filename'],sheet=source['sheet_name'],uploaded_at=source['uploaded_at']))
                    row['source_hashes'].append(source['file_sha256'])
            reports=[r for r in inventory if r['publication_id'] is not None]
            if any(r['status']!='published' for r in reports):raise ValueError('Status riwayat publikasi tidak konsisten.')
            return dict(current=current,reports=reports,inventory=inventory,readiness=assess_readiness(reports))
    finally:
        try:connection.rollback()
        finally:connection.close()
