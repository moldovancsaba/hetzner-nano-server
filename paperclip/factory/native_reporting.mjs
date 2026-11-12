import {createRequire} from 'node:module';
import fs from 'node:fs';
import crypto from 'node:crypto';
let input='';for await(const chunk of process.stdin){input+=chunk;if(input.length>16384)throw new Error('report_input_limit');}
const request=JSON.parse(input);
let sql;
try {
 if(process.env.DATABASE_URL)throw new Error('report_embedded_database_required');
 if(process.env.PAPERCLIP_DEPLOYMENT_MODE!=='local_trusted')throw new Error('report_private_deployment_required');
 if(!/^[a-f0-9-]{36}$/i.test(request.company))throw new Error('report_company_invalid');
 for(const [path,digest] of Object.entries(request.contract.files)){
  if(crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex')!==digest)throw new Error('native_read_contract_changed');
 }
 const require=createRequire('/app/packages/db/package.json');const postgres=require('postgres');const {drizzle}=require('drizzle-orm/postgres-js');
 const schema=await import('/app/packages/db/src/schema/index.ts');const {issueService}=await import('/app/server/src/services/issues.ts');
 const source=fs.readFileSync('/app/server/src/index.ts','utf8').split('const createEmbeddedPostgres')[1];
 const password=source.match(/password:\s*"([^"]+)"/)[1];const user=source.match(/user:\s*"([^"]+)"/)[1];
 const port=Number(fs.readFileSync('/paperclip/instances/default/db/postmaster.pid','utf8').split('\n')[3]);
 sql=postgres({host:'127.0.0.1',port,user,password,database:'paperclip',max:2,connect_timeout:5,onnotice:()=>{},connection:{default_transaction_read_only:'on',statement_timeout:15000}});
 const [{transaction_read_only}]=await sql`show transaction_read_only`;if(transaction_read_only!=='on')throw new Error('report_read_only_required');
 const companies=await sql`select id from companies where id=${request.company}::uuid`;if(companies.length!==1)throw new Error('report_company_missing');
 const rows=await issueService(drizzle(sql,{schema})).list(request.company,{limit:100001,sortField:'id',sortDir:'asc'});
 if(rows.length>100000||rows.some(row=>row.companyId!==request.company))throw new Error('report_scope_or_count_invalid');
 const fields=['id','companyId','identifier','title','description','status','parentId','projectId','assigneeAgentId','assigneeUserId','createdAt','updatedAt','completedAt','blockedTransitionAt'];
 const body=JSON.stringify({version:1,read_only:true,company:request.company,tasks:rows.map(row=>Object.fromEntries(fields.filter(key=>row[key]!==undefined).map(key=>[key,row[key]])))});
 if(Buffer.byteLength(body)>33554432)throw new Error('report_output_limit');
 await new Promise((resolve,reject)=>process.stdout.write(body,error=>error?reject(error):resolve()));
} catch(error){process.stderr.write(JSON.stringify({error:'native_reporting_unavailable',category:error.code||error.cause?.code||error.name}));process.exitCode=1;}
finally {if(sql)await sql.end();process.exit(process.exitCode||0);}
