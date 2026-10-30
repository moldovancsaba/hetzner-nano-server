"""Complete company issue list. The Paperclip API answers one page of 500 by default and at most 1000 per request."""
PAGE=1000
MAX_PAGES=100

def fetch(get,company):
 rows=[];seen=set();offset=0
 for _ in range(MAX_PAGES):
  page=get('/companies/'+company+'/issues?limit=%d&offset=%d'%(PAGE,offset))
  page=page if isinstance(page,list) else page.get('issues',[])
  fresh=[r for r in page if r['id'] not in seen]
  rows+=fresh;seen.update(r['id'] for r in fresh)
  # A page that adds nothing is the end, whatever page size the server really applies.
  if not fresh:break
  offset+=len(page)
 return rows
