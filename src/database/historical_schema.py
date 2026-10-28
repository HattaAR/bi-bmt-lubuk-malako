"""Explicit optional migration. Importing this module never executes DDL."""
TABLE_SQL='''CREATE TABLE fact_pembiayaan_historis (
 historical_fact_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
 dataset_version_id BIGINT UNSIGNED NOT NULL,
 source_file_id BIGINT UNSIGNED NOT NULL,
 source_sheet VARCHAR(128) NOT NULL,
 source_row_number INT UNSIGNED NOT NULL,
 realization_date DATE NULL, original_maturity_date DATE NULL, completion_date DATE NULL,
 original_principal DECIMAL(18,2) NULL, contract_duration_days INT UNSIGNED NULL,
 eligible BOOLEAN NOT NULL, target_late TINYINT NULL, completion_delay_days INT UNSIGNED NULL,
 date_issues JSON NOT NULL, raw_values JSON NOT NULL,
 UNIQUE KEY uq_historical_lineage(dataset_version_id,source_file_id,source_sheet,source_row_number),
 KEY idx_historical_year(dataset_version_id,realization_date),
 CONSTRAINT fk_hist_dataset FOREIGN KEY(dataset_version_id) REFERENCES dataset_versions(dataset_version_id),
 CONSTRAINT fk_hist_source FOREIGN KEY(source_file_id) REFERENCES source_files(source_file_id),
 CONSTRAINT ck_hist_target CHECK ((eligible=1 AND target_late IN (0,1) AND completion_delay_days IS NOT NULL
  AND realization_date IS NOT NULL AND original_maturity_date IS NOT NULL AND completion_date IS NOT NULL
  AND contract_duration_days IS NOT NULL AND original_maturity_date>=realization_date AND completion_date>=realization_date
  AND contract_duration_days=DATEDIFF(original_maturity_date,realization_date)
  AND target_late=(completion_date>original_maturity_date)
  AND completion_delay_days=GREATEST(0,DATEDIFF(completion_date,original_maturity_date)))
  OR (eligible=0 AND target_late IS NULL AND completion_delay_days IS NULL))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci'''


def apply_historical_schema(connection):
    """Operator action only. DDL auto-commits; never called by loader/UI."""
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE 'fact_pembiayaan_historis'")
        if cursor.fetchone():raise ValueError('Tabel historis sudah ada; tinjau migrasi, tidak ditimpa.')
        cursor.execute(TABLE_SQL)
        for operation,alias in (('INSERT','NEW'),('UPDATE','OLD'),('DELETE','OLD')):
            cursor.execute(f'''CREATE TRIGGER protect_historical_{operation.lower()} BEFORE {operation}
                ON fact_pembiayaan_historis FOR EACH ROW BEGIN
                IF EXISTS(SELECT 1 FROM dataset_publications WHERE dataset_version_id={alias}.dataset_version_id)
                 OR EXISTS(SELECT 1 FROM dataset_versions WHERE dataset_version_id={alias}.dataset_version_id AND status='published')
                THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Published historical facts are immutable'; END IF;
                {'IF NEW.dataset_version_id<>OLD.dataset_version_id THEN SIGNAL SQLSTATE \'45000\' SET MESSAGE_TEXT=\'Historical version cannot change\'; END IF;' if operation=='UPDATE' else ''}
                END''')
