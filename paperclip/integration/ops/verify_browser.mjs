/** Read-only production browser checks with an existing private, short-lived access session. */
import { chromium, expect } from '../../dashboard/node_modules/@playwright/test/index.mjs';
import { readFile, mkdir, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
const args=process.argv.slice(2);
const option=name=>args[args.indexOf(name)+1];
const cookieFile=option('--cookie-file'),artifacts=option('--artifacts-dir');
if(!args.includes('--cookie-file')||!args.includes('--artifacts-dir'))throw new Error('Explicit private session and artifact paths required');
if((await stat(cookieFile)).mode&0o077)throw new Error('Access session must be private');
await mkdir(artifacts,{recursive:true,mode:0o700});
const cookie=JSON.parse(await readFile(cookieFile,'utf8'));
if(cookie.url!=='https://paperclip.haho.ai/'||cookie.expires<Date.now()/1000||cookie.expires>Date.now()/1000+600)throw new Error('Expected a bounded Paperclip access session');
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE});
const report={checked_at:new Date().toISOString(),origin:'https://paperclip.haho.ai',mutating_requests_allowed:false,views:[]};
try{
 const context=await browser.newContext();await context.addCookies([cookie]);
 await context.route('**/*',route=>{
  if(!['GET','HEAD'].includes(route.request().method())||new URL(route.request().url()).origin!=='https://paperclip.haho.ai')return route.abort();
  return route.continue();
 });
 for(const [route,title,api] of [['/factory/','Company overview','/factory/metrics'],['/factory/exchange/','Paperclip and OpenClaw results','/factory/exchange-snapshot']]){
  const page=await context.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.name));
  const responsePromise=page.waitForResponse(response=>new URL(response.url()).pathname===api,{timeout:45000});
  await page.goto(report.origin+route,{waitUntil:'domcontentloaded',timeout:20000});
  const response=await responsePromise;if(response.status()!==200)throw new Error('Authenticated view data unavailable: '+response.status());
  await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  if(errors.length)throw new Error('Production browser encountered a script error');
  await page.screenshot({path:path.join(artifacts,route==='/factory/'?'company.png':'exchange.png'),fullPage:true});
  report.views.push({route,heading:title,authenticated_data_status:response.status(),script_errors:errors.length});
  await page.close();
 }
 await context.close();
 await writeFile(path.join(artifacts,'verification.json'),JSON.stringify(report,null,2)+'\n',{mode:0o600});
 process.stdout.write(JSON.stringify(report)+'\n');
}finally{await browser.close();}
