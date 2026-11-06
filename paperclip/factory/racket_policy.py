"""Racket Land's declared worldwide policy; legacy transport identities remain stable."""
import json
import re
import unicodedata
from pathlib import Path

ORIGIN='https://racket.land'

def countries():
 value=json.loads(Path(__file__).with_name('racket_countries.json').read_text())['codes']
 if not isinstance(value,dict) or len(set(value.values()))<240:raise ValueError('Worldwide country registry unavailable')
 return value

def validate(vertical):
 words=vertical.get('discovery',{}).get('vocabulary',{}).get('requiredTopicWords')
 if vertical.get('slug')!='racket-land' or vertical.get('territoryScope')!={'kind':'unrestricted'} or 'racket-club' not in vertical.get('taxonomy',{}) or not isinstance(words,list) or not 1<=len(words)<=100 or any(not isinstance(word,str) or not 2<=len(word)<=80 for word in words):raise ValueError('Racket Land application policy unavailable or changed')
 return vertical

def matches(text,vertical):
 validate(vertical)
 text=' '.join(unicodedata.normalize('NFKC',str(text)).casefold().split())
 return any(re.search(r'(?<!\w)'+re.escape(' '.join(word.casefold().split()))+r'(?!\w)',text) for word in vertical['discovery']['vocabulary']['requiredTopicWords'])
