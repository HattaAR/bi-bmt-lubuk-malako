"""Reuse the read-only monitoring snapshot and anonymous contract identifiers."""
from src.database.connection import get_connection
from src.database.monitoring import get_monitoring


def get_simulation_context(*,code=None,search='',expected_publication_id=None,connection_factory=get_connection):
    result=get_monitoring(scope='all',search=search,page_size=25,detail_code=code,
        expected_publication_id=expected_publication_id,connection_factory=connection_factory)
    return dict(publication=result['publication'],status=result['status'],choices=result['rows'],
                contract=result['detail'],contract_status=result['detail_status'],total_choices=result['summary']['contracts'])
