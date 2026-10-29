"""Fixed-origin Brave web search; key stays in the host environment, response stays in RAM."""
import json,os,time,urllib.error,urllib.parse,urllib.request
from search_budget import BudgetWait
class SearchError(ValueError):
 def __init__(self,code,retryable=False):self.code=code;self.retryable=retryable;super().__init__(code)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
class Brave:
 def __init__(self,budget,opener=None,sleep=time.sleep,country='US',language='en'):
  if (country,language) not in {('US','en'),('ZA','en'),('HU','hu')}:raise ValueError('Unconfigured search locale')
  self.budget=budget;self.opener=opener or urllib.request.build_opener(NoRedirect);self.sleep=sleep;self.country=country;self.language=language
 def search(self,query,token):
  key=os.environ.get('BRAVE_SEARCH_API_KEY')
  if not key:raise SearchError('Brave connection is not configured')
  for attempt in range(3):
   try:self.budget.dispatch(token);break
   except BudgetWait as error:
    delay=error.until-self.budget.clock()
    if not 0<delay<=3:raise
    self.sleep(delay+0.02)
  else:raise SearchError('Could not acquire the global request slot',True)
  args={'q':query,'count':20,'country':self.country,'search_lang':self.language,'safesearch':'strict','result_filter':'web','extra_snippets':'true','text_decorations':'false'}
  req=urllib.request.Request('https://api.search.brave.com/res/v1/web/search?'+urllib.parse.urlencode(args),headers={'X-Subscription-Token':key,'Accept':'application/json'})
  try:
   with self.opener.open(req,timeout=25) as response:
    headers={k:v for k,v in response.headers.items() if k.lower().startswith('x-ratelimit-')};body=response.read(2*1024*1024+1)
    self.budget.finish(token,'succeeded',response.status,headers)
    if len(body)>2*1024*1024:raise SearchError('Brave response exceeded the size limit')
    value=json.loads(body);rows=value.get('web',{}).get('results',[])
    if not isinstance(rows,list):raise SearchError('Invalid Brave result format')
    return rows[:20]
  except urllib.error.HTTPError as error:
   headers={k:v for k,v in error.headers.items() if k.lower().startswith('x-ratelimit-') or k.lower()=='retry-after'};self.budget.finish(token,'failed',error.code,headers)
   raise SearchError('Brave returned HTTP '+str(error.code),error.code==429 or error.code>=500) from None
  except SearchError:raise
  except Exception:
   self.budget.finish(token,'uncertain');raise SearchError('Brave response was not confirmed; attempt counted conservatively',True) from None
