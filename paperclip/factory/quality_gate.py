"""Deterministic, fail-closed write authorization; independent of model confidence."""
import datetime,json,re,time,urllib.parse,urllib.request
# publishing imports this module too; see the note at the top of publishing.py.
import publishing,formats
# The policy version recorded with every decision. factory.json's automatic_quality_gate.policy is informational only.
VERSION='classscout-auto-v6'
# Content-update allowlist: used by check_refresh (field_allowlist) and by refresh.ContactUpdates.apply.
FIELDS={'phone','email','shortDescription','longDescription'}
def contact_key(field,value):
 """Comparable form of a contact value. Phones compare by digits without a leading US country code, so +17184478667 equals (718) 447-8667; any other difference stays a difference."""
 value=str(value or '')
 if field=='phone':
  digits=re.sub(r'\D','',value);return digits[1:] if len(digits)==11 and digits.startswith('1') else digits
 return publishing.norm(value)

def contacts_match(draft,facts):
 return all(contact_key(k,draft.get(k,''))==contact_key(k,facts.get(k,'')) for k in ['website','phone','email'])

def unambiguous_contacts(facts):
 import evidence
 for field in ['phone','email','address']:
  keys=set();zips=set()
  for fact in facts:
   if fact['field']!=field:continue
   value=str(fact['value']).strip()
   if field=='phone':
    value=contact_key('phone',value)
   elif field=='address':
    street=evidence.street(value)
    units=re.findall(r'\b(?:suite|ste\.?|unit|floor)\s+([A-Za-z0-9-]+)',value,re.I)
    zips.update(re.findall(r'\b\d{5}(?:-\d{4})?\b',value[len(street or ''):]))
    value=evidence.address_key(street)+('|'+','.join(u.casefold() for u in units) if units else '') if street else publishing.norm(value)
   else:value=value.casefold()
   keys.add(value)
  if len(keys)>1 or len(zips)>1:return False
 return True

def qualified_media(media,proof,pages,draft):
 qualification=media.get('qualification') or {}
 return (media.get('status')=='ready' and qualification.get('status')=='accepted'
  and qualification.get('provenance') in {'official','authoritative'}
  and ((proof.get('image_placeholder') is True and publishing.category_banner(media))
   or media.get('originalUrl') in proof.get('image_candidates',[]) and media.get('sourceDocumentUrl') in [p['url'] for p in pages])
  and draft.get('image')==media.get('uploadedUrl') and bool(media.get('contentHash')))

def enabled(config,issue):
 return config.get('automatic_quality_gate',{}).get('enabled') is True and config.get('projects',{}).get(issue.get('projectId'))=='ClassScout'
# runtime_settings and visible_by_settings are not used by the production path: a client's display settings no longer
# decide catalog intake (see the comment in check_publication). They are kept for their tests.
def runtime_settings():
 from catalog import NoRedirect
 with urllib.request.build_opener(NoRedirect).open('https://classscout.ai/api/public/runtime-config?city=nyc',timeout=25) as response:
  raw=response.read(262145)
  if len(raw)>262144:raise ValueError('Public visibility settings exceeded their response bound')
  value=json.loads(raw)
 if value.get('city')!='nyc' or not isinstance(value.get('settings'),dict) or not value.get('version'):raise ValueError('Public visibility settings are unavailable')
 return value

def visible_by_settings(draft,settings):
 if settings.get('cityEnabled') is False or draft.get('borough') in settings.get('disabledRegions',[]):return False
 if 'classes' in settings.get('disabledBrowseCategories',[]):return False
 allow=settings.get('enabledActivityTypes',[]);deny=settings.get('disabledActivityTypes',[])
 return bool(draft.get('activityTypes')) and any(a not in deny and (a in allow if allow or a=='Capoeira' else True) for a in draft['activityTypes'])

def initialize(database):
 with database() as db:db.execute('CREATE TABLE IF NOT EXISTS automatic_decisions(packet_hash TEXT PRIMARY KEY,policy TEXT,kind TEXT,decision TEXT,report_json TEXT,created_at REAL,submitted_at REAL)')
def record(database,packet,kind,checks):
 initialize(database)
 report={'policy':VERSION,'kind':kind,'checks':checks,'passed':all(checks.values())}
 with database() as db:db.execute('INSERT INTO automatic_decisions VALUES(?,?,?,?,?,?,NULL) ON CONFLICT(packet_hash) DO UPDATE SET decision=excluded.decision,report_json=excluded.report_json',(packet,VERSION,kind,'pass' if report['passed'] else 'hold',json.dumps(report),time.time()))
 if not report['passed']:raise ValueError('Automatic quality hold: '+', '.join(k for k,v in checks.items() if not v))
 return report

def reserve(db,packet,config):
 # Shared transaction with the packet compare-and-set: attempts count even on lost replies.
 # One daily cap serves every write path that calls this (publication, refresh, program updates, engine intake and
 # publish, Padel intake). daily_write_limit defaults to 10 when absent and is never above 20.
 policy=config.get('automatic_quality_gate',{});cap=min(20,max(1,int(policy.get('daily_write_limit',10))))
 from zoneinfo import ZoneInfo
 now=datetime.datetime.now(ZoneInfo('Europe/Budapest'));start=now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
 row=db.execute('SELECT decision,submitted_at FROM automatic_decisions WHERE packet_hash=?',(packet,)).fetchone()
 if not row or row['decision']!='pass' or row['submitted_at']:raise ValueError('Automatic authorization is unavailable or was already consumed')
 if db.execute('SELECT count(*) FROM automatic_decisions WHERE submitted_at>=?',(start,)).fetchone()[0]>=cap:raise ValueError('Automatic daily write limit reached; no write sent')
 db.execute('UPDATE automatic_decisions SET submitted_at=? WHERE packet_hash=?',(time.time(),packet))

def descriptions(row,page):
 """Neutral, source-checked copy only; no guessed price, timetable or age claims."""
 n=publishing.norm;text=n(page['text'])
 if not all(isinstance(row.get(k),str) and row[k].strip() and n(row[k]) in text for k in ['name','address','neighborhood','borough']):return {}
 activities=row.get('activityTypes',[])
 if not isinstance(activities,list) or not activities or any(not isinstance(a,str) or n(a) not in text for a in activities):return {}
 short=row['name']+' offers '+', '.join(activities).lower()+' activities in '+row['neighborhood']+', '+row['borough']+'.'
 long=short+' The location is '+row['address']+'. Visit the official website for current program details, schedules and prices.'
 if len(short)>240 or len(long)>1200 or re.search(r'[<>\n\r]',short+long):return {}
 return {'shortDescription':short,'longDescription':long}

def check_refresh(database,packet,body,proof,baseline,page):
 n=publishing.norm;patch=body['patch'];facts=proof['facts'];expected=descriptions(baseline,page)
 contacts={f['field']:f['value'] for f in facts if f['field'] in {'phone','email'} and n(f['value']) in n(f['quote']) and n(f['quote']) in n(page['text'])}
 checks={'field_allowlist':bool(patch) and not set(patch)-FIELDS,'unclaimed_listing':not baseline['owner_managed'],'fresh_evidence':0<=time.time()-float(page['fetched_at'])<3600,'literal_contacts':all(k not in patch or patch[k]==v for k,v in contacts.items()) and all(k not in {'phone','email'} or contacts.get(k)==v for k,v in patch.items()),'grounded_content':all(k not in {'shortDescription','longDescription'} or expected.get(k)==v for k,v in patch.items()),'unambiguous_contacts':unambiguous_contacts(facts),'no_content_truncation':all(k not in patch or len(str(baseline.get(k) or ''))<=5000 for k in ['shortDescription','longDescription'])}
 return record(database,packet,'content_update',checks)

def check_publication(database,packet,issue,body,proof,pages):
 brief=publishing.parse_brief(issue)
 with database() as db:entity=db.execute('SELECT brand,status FROM entities WHERE id=?',(brief['Draft reference'],)).fetchone()
 normalized,fresh=publishing.normalize_sources(brief,pages,proof['facts']);draft=body['draftPayload'];n=publishing.norm
 core={'name':'title','address':'addressRaw','borough':'boroughRaw','neighborhood':'neighborhoodRaw','category':'categoryHint'}
 media=body.get('mediaResult') or {};qualification=media.get('qualification') or {};ages=fresh['ages'];lo=min(a['min'] for a in ages);hi=max(a['max'] for a in ages)
 schedules=fresh['schedules'];programs=draft.get('recurringPrograms',[])
 def schedule_ok(p,s):
  return p.get('daysOfWeek')==s['daysOfWeek'] and n(p.get('timeText'))==n(s['timeText']) and p.get('ageMinMonths')==formats.bounds(s,True)[0] and p.get('ageMaxMonths')==formats.bounds(s,True)[1] and p.get('price',{}).get('evidence')==fresh['price']['evidence'] and p.get('price',{}).get('amount')==fresh['price'].get('amount') and p.get('price',{}).get('unit')==fresh['price'].get('unit') and (not s.get('startDate') or p.get('startDate')==s['startDate'] and p.get('endDate')==s['endDate'])
 # Product-domain display toggles never authorize or prohibit shared catalog intake.
 checks={'independent_source_review':bool(entity and entity['brand']=='ClassScout' and entity['status']=='ready_for_human_review'),'source_identity':all(n(draft.get(k))==n(normalized[v]) for k,v in core.items()),'source_copy':draft.get('shortDescription')==normalized['descriptionFacts'][0] and draft.get('longDescription')==' '.join(normalized['descriptionFacts']),'class_price':(draft.get('pricePerClass')==0 and draft.get('price',{}).get('evidence')=='unknown' and not any(k in draft.get('price',{}) for k in ['amount','currency','unit'])) if fresh['price']['evidence']=='unknown' else (draft.get('pricePerClass')==fresh['price'].get('amount') and draft.get('price',{}).get('unit')==fresh['price'].get('unit') and draft.get('price',{}).get('amount')==fresh['price'].get('amount')),'age_bounds':draft.get('ageMinMonths')==min(formats.bounds(a)[0] for a in ages) and draft.get('ageMaxMonths')==max(formats.bounds(a)[1] for a in ages),'class_timetable':len(programs)==len(schedules) and all(schedule_ok(p,s) for p,s in zip(programs,schedules)),'official_contacts':contacts_match(draft,normalized['contactFacts']),'activity':draft.get('activityTypes')==normalized['activityTypesRaw'],'unclaimed_new_listing':not draft.get('ownerSub') and draft.get('claimStatus')=='unclaimed','qualified_image':qualified_media(media,proof,pages,draft),'https_sources':all(p['url'].startswith('https://') and 0<=time.time()-float(p['fetched_at'])<3600 for p in pages),'unambiguous_contacts':unambiguous_contacts(proof['facts'])}
 return record(database,packet,'new_listing',checks)
