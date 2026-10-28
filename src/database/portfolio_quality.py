"""Derived quality measures from an already pinned KPI snapshot; no second read."""
from decimal import Decimal, localcontext


def quality_summary(snapshot):
    rows = [row for row in snapshot['composition'] if row['code'] in {'KL', 'D', 'M'}]
    with localcontext() as context:
        context.prec = 50
        shares = {key: (sum((row[key] for row in rows), Decimal(0))
                        if snapshot['availability'][available] else None)
                  for key, available in (('contract_share_percent', 'contract_shares'),
                                         ('outstanding_share_percent', 'outstanding_shares'))}
    # Ties are reported together; zero/empty portfolios have no dominant category.
    maximum = max((row['outstanding_principal'] for row in rows), default=Decimal(0))
    leaders = [row['code'] for row in rows if row['outstanding_principal'] == maximum] if maximum > 0 else []
    return {'npf_shares': shares, 'leading_codes': leaders, 'leading_outstanding': maximum,
            'partial': snapshot['status'] == 'partial'}
