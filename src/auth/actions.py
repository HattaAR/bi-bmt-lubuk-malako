"""Protected UI entrypoints. No writes, global result caches, or account identifiers."""

from src.auth.session import require_role
from src.database.connection import get_connection


def read_upload_history(state, *, connection_factory=None):
    require_role(state, "admin")
    with (connection_factory or get_connection)() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT source_file_id,original_filename,byte_size,uploaded_at
                FROM source_files ORDER BY uploaded_at DESC,source_file_id DESC LIMIT 100""")
            rows = list(cursor.fetchall())
    require_role(state, "admin")
    return rows


def validate_local_sources(state):
    require_role(state, "admin")
    from src.etl.active_candidate import prepare_candidate

    candidate = prepare_candidate()
    require_role(state, "admin")
    return {"contracts": candidate.summary["rows"], "warnings":
            sum(finding.severity == "warning" for finding in candidate.findings)}


def read_executive_kpis(state, *, marketing_id=None, sector_id=None, include_context=False, connection_factory=None):
    require_role(state, "executive")
    from src.database.active_kpis import get_active_kpis

    result = get_active_kpis(marketing_id=marketing_id, sector_id=sector_id,
                            include_context=include_context,
                            connection_factory=connection_factory or get_connection)
    require_role(state, "executive")
    return result


def read_monitoring(state, *, connection_factory=None, **filters):
    require_role(state, 'executive')
    from src.database.monitoring import get_monitoring
    result=get_monitoring(connection_factory=connection_factory or get_connection, **filters)
    require_role(state, 'executive')
    return result


def read_concentration(state, *, connection_factory=None, **filters):
    require_role(state,'executive')
    from src.database.concentration import get_concentration
    result=get_concentration(connection_factory=connection_factory or get_connection,**filters)
    require_role(state,'executive')
    return result


def read_marketing_portfolio(state, *, marketing_id=None, sector_id=None, connection_factory=None):
    """Reuse one read-only grouped snapshot and the shared KPI denominators."""
    require_role(state,'executive')
    from src.database.concentration import get_concentration
    result=get_concentration(marketing_id=marketing_id,sector_id=sector_id,group_by='marketing',
                             connection_factory=connection_factory or get_connection)
    require_role(state,'executive')
    return result


def read_historical(state,*,connection_factory=None,**filters):
    require_role(state,'executive')
    from src.database.historical_analysis import get_historical_summary
    result=get_historical_summary(connection_factory=connection_factory or get_connection,**filters)
    require_role(state,'executive')
    return result


def read_simulation_context(state,*,connection_factory=None,**filters):
    require_role(state,'executive')
    from src.database.simulation import get_simulation_context
    result=get_simulation_context(connection_factory=connection_factory or get_connection,**filters)
    require_role(state,'executive')
    return result


def read_history_trends(state,*,connection_factory=None):
    require_role(state,'executive')
    from src.database.history_trends import get_history_trends
    result=get_history_trends(connection_factory=connection_factory or get_connection)
    require_role(state,'executive')
    return result
