
ALGOD_STATUS_KEYS = ['catchpoint', 'catchpoint-acquired-blocks', 'catchpoint-processed-accounts', 'catchpoint-processed-kvs', 'catchpoint-total-accounts', 'catchpoint-total-blocks', 'catchpoint-total-kvs', 'catchpoint-verified-accounts', 'catchpoint-verified-kvs', 'catchup-time', 'last-catchpoint', 'last-round', 'last-version', 'next-version', 'next-version-round', 'next-version-supported', 'stopped-at-unsupported-round', 'time-since-last-round']

def test_get_algod(algodcli, request):
    status = algodcli.status()
    assert [k for k in status.keys()] == ALGOD_STATUS_KEYS

    