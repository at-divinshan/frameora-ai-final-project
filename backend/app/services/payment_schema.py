"""Read-only prerequisite checks. No cached success, schema creation or repair."""
from sqlalchemy import inspect, UniqueConstraint, ForeignKeyConstraint, CheckConstraint, Boolean
from fastapi import HTTPException
from app.models.payment_preparation import PaymentCheckout, PaymentWebhookEvent, PaidCreditAllocation


def require_payment_schema(db):
    try:
        from app.services.subscription_service import require_schema
        require_schema(db)
        inspector = inspect(db.connection())
        if inspector.dialect.name != 'mysql': raise ValueError()
        for model in (PaymentCheckout,PaymentWebhookEvent,PaidCreditAllocation):
            table = model.__table__
            if not inspector.has_table(table.name): raise ValueError()
            columns = {c['name']:c for c in inspector.get_columns(table.name)}
            if any(c.name not in columns or columns[c.name]['nullable'] != c.nullable for c in table.columns): raise ValueError()
            if tuple(inspector.get_pk_constraint(table.name)['constrained_columns']) != tuple(table.primary_key.columns.keys()): raise ValueError()
            for c in table.columns:
                actual = columns[c.name]['type']
                if getattr(actual, 'length', None) != getattr(c.type, 'length', None): raise ValueError()
                if isinstance(c.type, Boolean):
                    if type(actual).__name__.lower() not in ('boolean', 'tinyint'): raise ValueError()
                elif actual._type_affinity is not c.type._type_affinity: raise ValueError()
            unique = {tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name)}
            unique.update(tuple(c['column_names']) for c in inspector.get_indexes(table.name) if c.get('unique'))
            for c in table.constraints:
                if isinstance(c,UniqueConstraint) and tuple(c.columns.keys()) not in unique: raise ValueError()
                if isinstance(c,ForeignKeyConstraint):
                    local=tuple(e.parent.name for e in c.elements)
                    remote=tuple(e.column.name for e in c.elements)
                    if not any(tuple(f['constrained_columns'])==local and f['referred_table']==c.referred_table.name
                        and tuple(f['referred_columns'])==remote and f.get('referred_schema') in (None,inspector.default_schema_name)
                        for f in inspector.get_foreign_keys(table.name)): raise ValueError()
            checks = {c['name'] for c in inspector.get_check_constraints(table.name)}
            if any(c.name not in checks for c in table.constraints if isinstance(c,CheckConstraint)): raise ValueError()
            options = inspector.get_table_options(table.name)
            if options.get('mysql_engine','').lower() != 'innodb': raise ValueError()
        # Check names alone cannot prove altered plan/date expressions. This runtime
        # check is additional to the mandatory manually reviewed release gate.
        for table, name in [('SubscriptionPlan','m003_chk_plan_code'),('Subscription','m003_chk_sub_kind'),('Subscription','m003_chk_sub_status_dates')]:
            check = next((c['sqltext'].lower() for c in inspector.get_check_constraints(table) if c['name']==name),'')
            if not all(code in check for code in ('starter','growth','unlimited')): raise ValueError()
    except Exception:
        raise HTTPException(503,'Payment database prerequisites have not been verified.') from None
