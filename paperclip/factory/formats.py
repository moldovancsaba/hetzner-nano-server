"""Exact source units and month-based age bounds for Classes and dated Camps."""
import datetime,re
AGE=r'ages?\s+(\d{1,3})\s*[-–]\s*(\d{1,3})(?:\s*(months?|years?))?'
WORDS={w:i for i,w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen'.split())}
NUMBER=r'(?:\d{1,3}(?:\.5)?|'+'|'.join(WORDS)+')'
STATED=r'\b(?:ages?:?|aged)\s+('+NUMBER+r')(?:\s*[-–—]\s*|\s+(?:to|through|thru)\s+)('+NUMBER+r')(?:\s*(months?|years?))?\b'
def number(text):return float(WORDS[text.lower()]) if text.lower() in WORDS else float(text)
def ages(text,exact_years=False):
 """Explicit stated ranges: "ages 5-12", "aged 4 to 11", "ages three to ten", "ages 2.5-3.5". Halves are kept exact in months; nothing is guessed."""
 rows=[]
 for m in re.finditer(STATED,text,re.I):
  lo,hi=number(m.group(1)),number(m.group(2));months=(m[3] or '').lower().startswith('month');half=lo!=int(lo) or hi!=int(hi)
  if months and half:continue
  a=int(lo) if months else int(lo*12);b=int(hi) if months else int(hi*12)+(0 if exact_years or hi!=int(hi) else 11)
  if not 0<=a<=b<=215:continue
  exact=months or half
  row={'min':a/12 if exact else int(lo),'max':b/12 if exact else int(hi),'min_months':a,'max_months':b,'quote':m[0],'unit':'month' if exact else 'year'}
  if not any(x['min_months']==a and x['max_months']==b for x in rows):rows.append(row)
 if not rows:raise ValueError('Missing explicit numerical child age ranges in months or years')
 return rows
def bounds(row,schedule=False):
 if schedule:return int(row.get('age_min_months',row['age_min']*12)),int(row.get('age_max_months',row['age_max']*12+11))
 return int(row.get('min_months',row['min']*12)),int(row.get('max_months',row['max']*12+11))
def schedules(text,kind='Classes',exact_years=False,allow_expired=False):
 pattern=r'\b'+AGE+r'\s*[-–:]?\s*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)s?\s+(\d{1,2}:\d{2}\s*[ap]m)\s*[,;]?\s*(\d{1,3})\s*minutes'
 rows=[]
 for m in re.finditer(pattern,text,re.I):
  lo,hi=int(m[1]),int(m[2]);months=(m[3] or '').lower().startswith('month');duration=int(m[6]);hour,minute=map(int,re.findall(r'\d+',m[5])[:2]);a=lo if months else lo*12;b=hi if months else hi*12+(0 if exact_years or kind=='Camps' else 11)
  if not 0<=a<=b<=215 or not 1<=hour<=12 or not 0<=minute<=59 or not 15<=duration<=(720 if kind=='Camps' else 240):continue
  row={'daysOfWeek':[m[4].capitalize()],'startTime':m[5],'timeText':m[5]+' ('+str(duration)+' minutes)','title':'Ages '+str(lo)+'–'+str(hi)+(' months' if months else ''),'summary':m[0],'age_min':a/12 if months else lo,'age_max':b/12 if months else hi,'age_min_months':a,'age_max_months':b,'quote':m[0]}
  if not any(x['summary'].casefold()==row['summary'].casefold() for x in rows):rows.append(row)
 if not rows:raise ValueError('Missing explicit age-specific program timetable and duration; facility hours are not a program timetable')
 if kind=='Camps':
  dates=re.findall(r'\bcamp dates?\s*:\s*(\d{4}-\d{2}-\d{2})\s+(?:to|through)\s+(\d{4}-\d{2}-\d{2})',text,re.I)
  if len(set(dates))!=1:raise ValueError('Camps require one explicit ISO start/end date range')
  start,end=map(datetime.date.fromisoformat,dates[0])
  if start>end or (end<datetime.datetime.now(datetime.timezone.utc).date() and not allow_expired) or (end-start).days>120:raise ValueError('Camp dates are expired, reversed or outside the supported season span')
  for row in rows:row.update(startDate=start.isoformat(),endDate=end.isoformat())
 return rows
def price(text,kind='Classes'):
 matches=list(re.finditer(r'\$(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:per\s+|/\s*)(class|month|term|semester|week|day|session)\b',text,re.I))
 values={(float(m[1].replace(',','')),m[2].lower()) for m in matches}
 allowed={'class','month','term','semester'} if kind=='Classes' else {'day','week','session'}
 if len(values)!=1:raise ValueError('Missing or ambiguous stated program price/unit; fees are never divided into guessed per-class amounts')
 amount,unit=next(iter(values))
 if unit not in allowed or not 0<amount<=50000:raise ValueError('Stated fee unit/amount is unsupported for this format')
 return {'evidence':'stated','amount':amount,'currency':'USD','unit':unit,'sourceText':matches[0][0]}
def price_sentence(price):
 return 'A single class costs $'+format(price['amount'],'g')+'.' if price['unit']=='class' else 'The stated fee is $'+format(price['amount'],'g')+' per '+price['unit']+'.'

def age_evidence(rows):
 parts=[]
 for row in rows:
  parts.append(row['quote'])
  if row.get('unit')=='month':parts.append(str(row['min_months'])+' months to '+str(row['max_months'])+' months')
  elif row.get('max_months')==row['max']*12:parts.append(str(row['min'])+' years to '+str(row['max'])+' years')
 return '; '.join(parts)
