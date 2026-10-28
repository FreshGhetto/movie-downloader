import json
import pytest
from services.core import safe_name, unique_base, metadata, progress, command, validate_url

def test_names():
    assert safe_name('CON') == '_CON'
    assert safe_name('Film: città / notte?', '2024') == 'Film_ città _ notte_ (2024)'
    assert safe_name(' .. ') == 'Video'
    assert '%' not in safe_name('100% cinema')
    assert safe_name('LPT9.txt').startswith('_')

def test_collision(tmp_path):
    (tmp_path/'Film.mp4').touch()
    assert unique_base(tmp_path,'Film').name == 'Film (2)'
    assert unique_base(tmp_path,'Nuovo',[str(tmp_path/'Nuovo')]).name == 'Nuovo (2)'
    (tmp_path/'Film [ITA].mp4').touch()
    assert unique_base(tmp_path,'Film [ITA]').name == 'Film [ITA] (2)'

def test_metadata():
    result=metadata({'title':'Città','formats':[{'height':720,'vcodec':'h264'},{'height':1080,'has_drm':True},{'height':480,'vcodec':'h264'}]})
    assert result['heights']==[720,480]
    assert metadata({})['title']=='Video'
    with pytest.raises(ValueError): metadata({'has_drm':True})
    with pytest.raises(ValueError): metadata({'_type':'playlist'})

def test_progress():
    p=progress('MD_PROGRESS:'+json.dumps({'downloaded_bytes':50,'total_bytes_estimate':200,'speed':10,'eta':15}))
    assert p['percent']==25 and p['eta']==15
    assert progress('MD_PROGRESS:invalid') is None
    assert progress('[download] Destination: test.mp4') is None
    assert progress('MD_PROGRESS:{"downloaded_bytes":10}')['percent']==0

def test_command():
    args=command('yt-dlp.exe',{'base':'C:/Film/100_ città','url':'https://example.org/v','quality':'1080','fragments':8},'ffmpeg.exe')
    assert args[-2:]==['--','https://example.org/v']
    assert '[height<=1080]' in args[args.index('-f')+1]
    assert args[args.index('--concurrent-fragments')+1]=='8'
    assert '--ignore-config' in args and '--allow-unplayable-formats' not in args

def test_url():
    with pytest.raises(ValueError): validate_url('file:///C:/file.mp4')
    with pytest.raises(ValueError): validate_url('--exec calc')
