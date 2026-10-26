import csv,io
import pytest
from scripts.profile_public_domains import parse_csv,profile,HEADERS


def encoded(rows):
    s=io.StringIO();w=csv.writer(s);w.writerow(HEADERS);w.writerows(rows)
    return s.getvalue().encode('utf-8-sig')


def test_csv_preserves_empty_and_unicode_strings():
    row=['']*len(HEADERS);row[2]='여부C1';row[5]='001';row[10]='Y, N'
    parsed=parse_csv(encoded([row]))
    assert parsed[0]['데이터길이']=='001'
    assert parsed[0]['허용값']=='Y, N'
    assert parsed[0]['단위']==''


@pytest.mark.parametrize('row', [['x'], ['x']*(len(HEADERS)+1)])
def test_bad_row_width(row):
    with pytest.raises(ValueError):parse_csv(encoded([row]))


def test_wrong_headers():
    with pytest.raises(ValueError):parse_csv(b'name,type\nA,CHAR\n')


def test_unpinned_bytes_rejected():
    with pytest.raises(ValueError,match='pinned'):profile(encoded([['']*len(HEADERS)]))
