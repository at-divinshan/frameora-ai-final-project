"""Approved catalogue only; never activates subscriptions or grants credits."""
import json
from pathlib import Path

CATALOGUE_PATH = Path(__file__).resolve().parents[3] / 'user-subscription-plans.json'


def catalogue():
    plans = json.loads(CATALOGUE_PATH.read_text())
    return {
        'plans': [dict(plan, billing_period='month', activation_available=False,
                       availability='monthly_allowance_pending' if plan['code'] == 'free' else 'payment_setup_pending')
                  for plan in plans],
        'generation_policy': 'one_time_free_request',
        'monthly_credits_active': False,
    }
