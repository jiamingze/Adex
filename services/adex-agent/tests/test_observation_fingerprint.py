from adex_agent.execution.evidence import observation_fingerprint,cards_fingerprint


def test_observation_identity_ignores_fetch_time_order_whitespace_and_duplicates():
    one={'url':'https://example.com/item','title':'Item','snippet':'price  800','fetched_at':'2026-10-22'}
    two={**one,'snippet':'price 800','fetched_at':'2026-10-23'}
    assert observation_fingerprint([one,one])==observation_fingerprint([two])
    assert observation_fingerprint([one])!=observation_fingerprint([{**one,'snippet':'price 801'}])
    assert observation_fingerprint([]) is None
    assert cards_fingerprint([{'type':'source_list','data':{'items':[one]}}])==observation_fingerprint([one])
