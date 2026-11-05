"""Project-specific native writer holds for independently reviewed destination handoff."""


def require_native_destination_writer(config,issue,application,client):
 settings=config.get('source_exchange',{});handoffs=settings.get('destination_handoffs',{})
 if not isinstance(handoffs,dict):raise ValueError('Destination handoff configuration requires review')
 project=issue.get('projectId')
 if project not in handoffs:return
 expected={'application':application,'client':client};handoff=handoffs[project]
 allowed={'management':{'padel-africa','sportolok'},'salesleadgenerator':{'cogmap','seyu','dvsc'}}
 if (application not in allowed or client not in allowed[application] or settings.get('projects',{}).get(project)!=expected
     or not isinstance(handoff,dict) or handoff.get('scope')!=expected or handoff.get('writer')!='openclaw'
     or type(handoff.get('writer_epoch')) is not int or handoff['writer_epoch']<1
     or not isinstance(handoff.get('review_ref'),str) or not 1<=len(handoff['review_ref'])<=200):
  raise ValueError('Destination handoff does not match the reviewed project authority')
 raise ValueError('Destination writes are delegated to the assigned external writer. Preserve existing packets and reconcile uncertain effects before changing authority.')
