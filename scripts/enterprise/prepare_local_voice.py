"""Download the optional offline voice model from its official source."""
import json, urllib.request, hashlib
from pathlib import Path

root=Path(__file__).resolve().parents[2]
repo='Systran/faster-whisper-base'
with urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'?blobs=true',timeout=30) as response:
    info=json.load(response)
revision=info['sha']
target=root/'.runtime'/'models'/'faster-whisper-base'
target.mkdir(parents=True,exist_ok=True)
files={'config.json','model.bin','tokenizer.json','vocabulary.json','vocabulary.txt','preprocessor_config.json'}
for entry in info['siblings']:
    name=entry['rfilename']
    if name not in files:continue
    path=target/name
    expected=entry.get('lfs',{}).get('sha256')
    if path.exists() and (not expected or hashlib.sha256(path.read_bytes()).hexdigest()==expected):
        print('Ready '+name,flush=True);continue
    print('Downloading '+name,flush=True)
    part=path.with_suffix(path.suffix+'.part')
    digest=hashlib.sha256()
    with urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+revision+'/'+name,timeout=60) as source,part.open('wb') as output:
        while chunk:=source.read(1024*1024):output.write(chunk);digest.update(chunk)
    if expected and digest.hexdigest()!=expected:raise RuntimeError('Checksum mismatch: '+name)
    part.replace(path)
    print('Ready '+name+' '+str(path.stat().st_size),flush=True)
(target/'source.json').write_text(json.dumps({'repo':repo,'revision':revision},indent=2))
print('Offline model ready',flush=True)
