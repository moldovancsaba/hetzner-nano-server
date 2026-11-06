"""Route fixed factory workflows to the existing five roles."""
import catalog
# Workflow kind -> the role that must run it (checked in run). Routines are listed in workflows.json; the issue-driven kinds
# (prepare_listing, refresh_provider, program_update, engine_candidate, racket_candidate) are created by other workflows.
ROLES={'autonomous_coordination':'support','sales_connection':'support','sales_pipeline':'support','sales_briefing':'support','verify_catalog':'support','refresh_provider':'publication','publication_queue':'publication','audit_site':'quality','operations_digest':'support','support_answer':'support','prepare_listing':'publication','growth_dispatch':'search','recover_evidence':'support','racket_maintenance':'support','racket_intake':'support','racket_discovery':'search','racket_candidate':'support','reliability_round':'support','freshness_round':'support','knowledge_round':'support','program_queue':'support','program_update':'publication','engine_maintenance':'support','engine_discovery':'search','engine_candidate':'support','management_overview':'support'}
def workflow(issue):return catalog.field(issue,'Factory workflow')
def run(issue,board,config,web,database,execution):
 kind=workflow(issue);role=config['agents'][execution['agent_id']]['role'];brand=config['projects'].get(issue.get('projectId'))
 if kind not in ROLES or ROLES[kind]!=role:raise ValueError('Assign this workflow to its configured factory role')
 if kind=='autonomous_coordination':
  import autonomy
  return autonomy.run(issue,board,config,web,database,execution)
 if kind.startswith('sales_'):
  import slg
  return slg.run(issue,board,config,web,database,execution)
 if kind in {'engine_maintenance','engine_discovery','engine_candidate','management_overview'}:
  import engine_ops
  return {'engine_maintenance':engine_ops.maintain,'engine_discovery':engine_ops.discover,'engine_candidate':engine_ops.candidate,'management_overview':engine_ops.overview}[kind](issue,board,config,web,database,execution)
 if kind=='program_update':
  if brand!='ClassScout':raise ValueError('Program updates require ClassScout')
  import program_updates
  return program_updates.run(issue,board,config,web,database,execution)
 if kind=='program_queue':
  import portfolio
  return portfolio.program_queue(issue,board,config,web,database,execution)
 if kind in {'racket_discovery','racket_candidate'}:
  # The engine client is the only Racket Land path; there is no fallback to a second implementation.
  import racket_land
  if not config.get('engine_clients',{}).get(racket_land.CLIENT):raise ValueError('The Racket Land engine client is not configured')
  import engine_ops
  return (engine_ops.discover if kind=='racket_discovery' else engine_ops.candidate)(issue,board,config,web,database,execution)
 if kind in {'reliability_round','freshness_round','knowledge_round'}:
  import company_ops
  return company_ops.run(issue,board,config,web,database,execution)
 if kind in {'racket_maintenance','racket_intake'}:
  if brand!='Racket Land' or not config.get('racket_enabled'):raise ValueError('Racket Land connector is disabled or assigned to the wrong brand')
  import racket_land
  return racket_land.run(issue,board,config,web,database,execution)
 if kind!='operations_digest' and brand!='ClassScout':raise ValueError('Operational workflows are enabled only for ClassScout')
 if not config.get('operational_workflows_enabled'):raise ValueError('Operational factory workflows are disabled')
 if kind=='recover_evidence':
  import evidence
  return evidence.run_queue(issue,board,config,web,database,execution)
 if kind=='growth_dispatch':
  import growth
  return growth.run(issue,board,config,web,database,execution)
 if kind=='prepare_listing':
  import publishing
  return publishing.run(issue,board,config,web,database,execution=execution)
 if kind=='verify_catalog':return catalog.run(issue,board,config,web,database,execution)
 if kind=='refresh_provider':
  import refresh
  return refresh.run(issue,board,config,web,database,execution)
 if kind=='publication_queue':
  import pipeline
  return pipeline.run_queue(issue,board,config,web,database,execution)
 if kind=='audit_site':
  import site_audit
  return site_audit.run(issue,board,config,web,database,execution)
 if kind=='operations_digest':
  import operations_digest
  return operations_digest.run(issue,board,config,web,database,execution)
 if kind=='support_answer':
  import support
  return support.run(issue,board,config,web,database,execution)
