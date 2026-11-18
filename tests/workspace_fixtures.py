"""Explicit authored comparison decisions for software integration fixtures."""
from apps.factory_lab import policy_agreement as agreement
from tests.test_preparation import approved as preparation_approved


def compared(draft):
    for entry in draft['entries']:
        if entry['kind']=='policy' and entry['status']=='approved' and entry['target'] not in ('context','unsupported',''):
            draft=agreement.review(draft,entry['id'],agreement.status(draft,entry['id'])['binding'],
                                   'agrees','before_discount' if entry['target'] in ('shipping','coupon') else 'not_applicable',
                                   'Authored fixture comparison for software tests; not an independent policy assessment.')
    return draft


def approved():
    return compared(preparation_approved())
