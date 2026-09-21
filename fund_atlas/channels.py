"""Channel capabilities are separate from today's subscription status."""
LABELS = {'exchange': '场内买卖', 'otc': '场外申购', 'both': '两者均可', 'unknown': '渠道待核验'}


def classify_channel(fund):
    code = str(fund.get('code', ''))
    name = fund.get('name', '').upper()
    # Listing flags are legacy heuristics: require a matching share code as well.
    listed = bool(fund.get('listed')) and code.startswith(('15', '16', '50', '51', '52', '56', '58'))
    if listed and 'LOF' in name:
        return 'both'
    if listed and 'ETF' in name and '联接' not in name and '连接' not in name:
        return 'exchange'
    if not listed and (code.startswith(('0', '1', '2', '3', '4', '5', '9'))):
        return 'otc'
    return 'unknown'
