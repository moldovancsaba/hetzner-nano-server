#!/usr/bin/env python3
"""Compare the Paperclip host with this repository, file by file, and fail on any difference nobody has written down.

Usage: python3 scripts/check_paperclip_drift.py [--host root@IP] [--identity KEY] [--strict] [--write-baseline]
Read-only: one ssh session hashes the deployed files, plus a plain read of the two files that need normalising.
Nothing is copied to the host and no secret value is printed or stored. A value in the live Caddyfile that follows
header_up Authorization or a token or key header is replaced by <redacted> on both sides before comparing.

Each mapped file is SAME, KNOWN, STALE or DRIFT. KNOWN means the two sides differ exactly as paperclip/drift-baseline.json
records (hashes and reason), which is how a repository change that is waiting for a release stays visible without failing.
STALE means a recorded difference no longer matches (one side changed since it was reviewed) and DRIFT means a difference
nobody recorded; both exit 1, so a hand edit on the host or an unreleased repository edit cannot go unnoticed. After a
release, remove the entry. --strict also fails on code files found on the host that the repository does not map.
--write-baseline records the current differences with the reason "unreviewed"; replace each reason before committing.
"""
import argparse,hashlib,json,os,pathlib,re,shlex,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASELINE=ROOT/'paperclip/drift-baseline.json'
HOST='root@2.29.113.132'
# Files of paperclip/ that are installed in /opt/narimato-paperclip, and the two the access gate lives in.
TOP={n:n for n in ('backup.py','backup_retention.py','restore-drill.py','scheduled-backup.py','archive_snapshot.py','snapshot.sh','configure-slg.py','compose.yaml','company.json','local-ai.json','image-metadata.json')}
TOP.update({'gate.py':'access/gate.py','login.html':'access/login.html'})
# Runtime files of the source exchange at its top level; ops/ and the *-verification.json evidence are repository-only.
EXCHANGE_TOP={'config.example.json','openapi.json','release-manifest.json','requirements-runtime.txt','acceptance-scenarios.json','examples.json','planning-validation.json'}
UNITS={'paperclip/factory/narimato-factory.service':'narimato-factory.service','paperclip/paperclip-access.service':'paperclip-access.service','paperclip/integration/source-exchange.service':'source-exchange.service','config/narimato-external-watchdog.service':'narimato-external-watchdog.service'}
SECRET_HEADER=re.compile(r'(?mi)^(\s*header_up\s+(?:Authorization|\S*(?:token|key|secret|ingress)\S*)\s+).*$')
def normalise_caddy(text):
 """The live Caddyfile and its repository copy differ only in secret header values, which are never stored."""
 return SECRET_HEADER.sub(r'\1<redacted>',text)
def normalise_json(text,ignore=()):
 """Canonical JSON without the settings the baseline lists as inert (dotted names, one level deep)."""
 data=json.loads(text)
 for dotted in ignore:
  head,_,tail=dotted.partition('.')
  if tail and isinstance(data.get(head),dict):data[head].pop(tail,None)
  elif not tail:data.pop(head,None)
 return json.dumps(data,sort_keys=True,separators=(',',':'))
def sha(text):return hashlib.sha256(text.encode('utf8')).hexdigest()
def tracked(prefix):
 names=subprocess.check_output(['git','ls-files',prefix],cwd=ROOT,text=True).split('\n')
 return [n for n in names if n and not n.endswith('.md') and '__pycache__' not in n and not pathlib.PurePosixPath(n).name.startswith('test_')]
def mapping():
 """(repository path, host path, kind) for every file the repository says is deployed. kind: file, caddy or json."""
 out=[(n,'/opt/narimato-factory/'+n[len('paperclip/factory/'):],'json' if n.endswith('factory.json') else 'file') for n in tracked('paperclip/factory/') if n.count('/')==2]
 out+=[('paperclip/'+n,'/opt/narimato-paperclip/'+h,'file') for n,h in TOP.items()]
 out+=[(n,'/opt/source-exchange/'+n[len('paperclip/integration/'):],'file') for n in tracked('paperclip/integration/') if n[len('paperclip/integration/'):].startswith('exchange/') or n[len('paperclip/integration/'):] in EXCHANGE_TOP]
 out+=[(n,'/etc/systemd/system/'+h,'file') for n,h in UNITS.items()]
 out+=[('operations/'+n,'/opt/narimato-external-watchdog/operations/'+n,'file') for n in ('alerts.py','external_watchdog.py','notifications.py')]
 out+=[('paperclip/Caddyfile','/etc/caddy/Caddyfile','caddy'),('paperclip/source-exchange-dashboard.caddy.example','/etc/caddy/source-exchange-dashboard.caddy','caddy')]
 return out
def ssh(host,identity,remote,stdin=None):
 cmd=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15']+(['-i',identity] if identity else [])+[host,remote]
 return subprocess.run(cmd,input=stdin,capture_output=True,text=True,check=True).stdout
def host_hashes(host,identity,items):
 """Hash of every plain file on the host, and normalised hash of the caddy and json kinds (read, never printed)."""
 plain=[p for _,p,k in items if k=='file'];script=''.join('if [ -f %s ]; then sha256sum -- %s; else echo MISSING %s; fi\n'%((shlex.quote(p),)*3) for p in plain)
 result={}
 for line in ssh(host,identity,'sh -s',script).splitlines():
  head,_,path=line.partition(' ');path=path.lstrip(' *')
  result[path]=None if head=='MISSING' else head
 ignore=baseline_ignore()
 for repo,path,kind in items:
  if kind=='file':continue
  try:text=ssh(host,identity,'cat '+shlex.quote(path))
  except subprocess.CalledProcessError:result[path]=None;continue
  result[path]=sha(normalise_caddy(text) if kind=='caddy' else normalise_json(text,ignore.get(repo,())))
 return result
def repo_hash(repo,kind):
 file=ROOT/repo
 if not file.is_file():return None
 text=file.read_text(encoding='utf8')
 if kind=='caddy':return sha(normalise_caddy(text))
 if kind=='json':return sha(normalise_json(text,baseline_ignore().get(repo,())))
 return hashlib.sha256(file.read_bytes()).hexdigest()
def baseline():return json.loads(BASELINE.read_text()) if BASELINE.is_file() else {'accepted':{},'ignored_json_keys':{},'server_only_ok':[]}
def baseline_ignore():return baseline().get('ignored_json_keys',{})
def classify(repo_side,host_side,accepted):
 """repo_side and host_side map a repository path to a hash (None when the file is absent). Returns {path: status}."""
 result={}
 for path,mine in repo_side.items():
  theirs=host_side.get(path)
  if mine==theirs:result[path]='SAME';continue
  note=accepted.get(path)
  if note is None:result[path]='DRIFT'
  elif note.get('server')==theirs and note.get('repo')==mine:result[path]='KNOWN'
  else:result[path]='STALE'
 return result
def server_only(host,identity,items,known):
 """Code files on the host that no repository file maps to (the staging trees and evidence JSON are deliberately skipped)."""
 mapped={p for _,p,_ in items}
 listing=ssh(host,identity,"find /opt/narimato-factory /opt/narimato-paperclip /opt/source-exchange -maxdepth 2 -type f \\( -name '*.py' -o -name '*.sh' -o -name '*.service' \\) -not -path '*/staging/*' -not -path '*/venv/*' -not -name 'test_*' -not -path '*/__pycache__/*'")
 return sorted(p for p in listing.split() if p not in mapped and p not in known)
def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__.split('\n')[0]);parser.add_argument('--host',default=os.environ.get('PAPERCLIP_HOST',HOST));parser.add_argument('--identity',default=os.environ.get('PAPERCLIP_SSH_KEY',os.path.expanduser('~/.ssh/hetzner_ai')))
 parser.add_argument('--strict',action='store_true');parser.add_argument('--write-baseline',action='store_true')
 args=parser.parse_args(argv);items=mapping();base=baseline()
 try:hosts=host_hashes(args.host,args.identity,items)
 except (subprocess.CalledProcessError,OSError) as error:print('error: cannot read the host:',getattr(error,'stderr',error));return 2
 repo_side={r:repo_hash(r,k) for r,_,k in items};host_side={r:hosts.get(p) for r,p,_ in items}
 status=classify(repo_side,host_side,base['accepted'])
 if args.write_baseline:
  base['accepted']={r:{'server':host_side[r],'repo':repo_side[r],'reason':base['accepted'].get(r,{}).get('reason','unreviewed')} for r,s in status.items() if s!='SAME'}
  BASELINE.write_text(json.dumps(base,indent=1,sort_keys=True)+'\n');print('baseline written:',len(base['accepted']),'entries');return 0
 counts={}
 for r,s in sorted(status.items()):
  counts[s]=counts.get(s,0)+1
  if s!='SAME':print('%-6s %s%s'%(s,r,'  ('+base['accepted'][r]['reason']+')' if s=='KNOWN' else ''))
 extra=server_only(args.host,args.identity,items,set(base.get('server_only_ok',[])))
 for p in extra:print('SERVER-ONLY',p)
 print('summary:',', '.join('%s %d'%(k,v) for k,v in sorted(counts.items())),'| server-only code files:',len(extra))
 return 1 if counts.get('DRIFT') or counts.get('STALE') or (args.strict and extra) else 0
if __name__=='__main__':sys.exit(main())
