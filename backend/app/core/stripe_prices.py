"""Approved sandbox Price IDs, selected exclusively from the authenticated role."""
from dataclasses import dataclass
from fastapi import HTTPException
from app.core.owner_plans import BY_CODE
from app.services.user_subscription_catalogue import catalogue

PRICE_IDS = {
    ('user','starter'): 'price_1UbwQY0AIz9Esgr8Km6SmqC1',
    ('user','pro'): 'price_1UbwUl0AIz9Esgr845GBoeQF',
    ('owner','starter'): 'price_1UbwaP0AIz9Esgr8CPe04N39',
    ('owner','growth'): 'price_1Ubwbk0AIz9Esgr85sCh27ZK',
    ('owner','unlimited'): 'price_1Ubwd20AIz9Esgr8vvcyskSz',
}

@dataclass(frozen=True)
class PaidPlan:
    role: str
    code: str
    name: str
    price_id: str
    amount_minor: int
    credits: int
    currency: str = 'lkr'
    max_projects: int | None = None
    max_share_links: int | None = None


def paid_plan(role, code):
    if role not in ('user','owner'):
        raise HTTPException(403,'Payments are available only to customers and studio owners.')
    if (role,code) not in PRICE_IDS:
        raise HTTPException(422,'This paid plan is not available for your account role.')
    if role == 'owner':
        p=BY_CODE[code]
        return PaidPlan(role,code,p.name,PRICE_IDS[(role,code)],p.price*100,p.credits,
            max_projects=p.max_projects,max_share_links=p.max_share_links)
    p=next(p for p in catalogue()['plans'] if p['code']==code)
    return PaidPlan(role,code,p['name'],PRICE_IDS[(role,code)],p['price']*100,p['credits'])


def purchase_plan(purchase):
    plan=paid_plan(purchase.role,purchase.plan_code)
    if (purchase.amount_minor,purchase.currency,purchase.credits)!=(plan.amount_minor,plan.currency,plan.credits):
        raise HTTPException(409,'Saved purchase does not match the approved role-specific plan.')
    return plan


def checkout_metadata(purchase):
    plan=purchase_plan(purchase)
    return {'checkout_id':str(purchase.id),'user_id':str(purchase.user_id),
            'plan_code':purchase.plan_code,'role':plan.role,'price_id':plan.price_id}
