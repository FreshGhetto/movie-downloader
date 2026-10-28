import subprocess
from unittest.mock import patch
import pytest
from services.workers import analyze, search_tmdb

def test_unsupported_link():
    result=subprocess.CompletedProcess([],1,'','ERROR: Unsupported URL')
    with patch('services.workers.subprocess.run',return_value=result):
        with pytest.raises(ValueError,match='non supportato'):
            analyze('yt-dlp.exe','https://example.org/missing')

def test_metadata_command_is_download_free():
    result=subprocess.CompletedProcess([],0,'{"title":"Film","formats":[]}','')
    with patch('services.workers.subprocess.run',return_value=result) as run:
        assert analyze('yt-dlp.exe','https://example.org/video')['title']=='Film'
        args=run.call_args.args[0]
        assert '--skip-download' in args and '--dump-single-json' in args
        assert not run.call_args.kwargs.get('shell',False)

def test_tmdb_missing_key():
    with pytest.raises(ValueError,match='chiave API'):
        search_tmdb('film','','movie')

@pytest.mark.parametrize('credential',['aaa.bbb.ccc','Bearer aaa.bbb.ccc'])
def test_tmdb_token(credential):
    from unittest.mock import Mock
    response=Mock(status_code=200)
    response.json.return_value={'results':[{'title':'Film italiano','release_date':'2024-01-01'}]}
    with patch('services.workers.requests.get',return_value=response) as get:
        assert search_tmdb('Film',credential,'movie')[0]['title']=='Film italiano'
        assert get.call_args.kwargs['headers']['Authorization']=='Bearer aaa.bbb.ccc'
        assert 'api_key' not in get.call_args.kwargs['params']

def test_tmdb_api_key():
    from unittest.mock import Mock
    response=Mock(status_code=200)
    response.json.return_value={'results':[]}
    with patch('services.workers.requests.get',return_value=response) as get:
        search_tmdb('Film','  chiave-v3  ','tv')
        assert get.call_args.kwargs['params']['api_key']=='chiave-v3'
        assert get.call_args.kwargs['headers']=={}


@pytest.mark.parametrize('current,latest,up_to_date', [
    ('2.2.0', 'v2.1.1', True),
    ('2.2.0', 'v2.2.0', True),
    ('2.2.0', 'v2.2.1', False),
    ('2.9.0', 'v2.10.0', False),
])
def test_update_check_does_not_offer_downgrades(current, latest, up_to_date):
    from unittest.mock import Mock
    from services.workers import check_app_update
    response = Mock(status_code=200)
    response.json.return_value = {'tag_name': latest, 'html_url': 'https://github.com/example/releases/latest'}
    with patch('services.workers.requests.get', return_value=response):
        result = check_app_update(current)
    assert result.get('up_to_date', False) is up_to_date
    if not up_to_date:
        assert result['version'] == latest.lstrip('v')
