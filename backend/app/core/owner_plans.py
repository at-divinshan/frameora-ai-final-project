"""Approved application catalogue. Never seeds or changes database plan rows."""
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class OwnerPlan:
    code: str
    name: str
    credits: int
    price: int
    max_projects: int | None
    max_share_links: int | None
    trial_days: int | None = None
    currency: str = 'LKR'

PLANS = (
    OwnerPlan('basic', 'Free Basic', 10, 0, 2, 3),
    OwnerPlan('trial', 'Free Trial', 100, 0, None, None, 14),
    OwnerPlan('starter', 'Starter', 100, 1500, 10, 20),
    OwnerPlan('growth', 'Growth', 250, 2500, 30, 60),
    OwnerPlan('unlimited', 'Unlimited', 500, 3500, None, None),
)
BY_CODE = {plan.code: plan for plan in PLANS}
PAID_CODES = frozenset(('starter', 'growth', 'unlimited'))

def catalogue():
    return {'plans': [dict(asdict(plan),
        credit_period='trial_total' if plan.code == 'trial' else 'monthly_anniversary',
        activation_available=plan.code in ('basic', 'trial')) for plan in PLANS]}

def validate_limit(limit):
    if limit is not None and (type(limit) is not int or limit < 0):
        raise ValueError('Invalid plan limit')
    return limit

def limit_reached(count, limit):
    validate_limit(limit)
    return limit is not None and count >= limit
