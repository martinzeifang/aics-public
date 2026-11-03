import { firefox } from 'playwright'
import fs from 'node:fs'
const BASE='https://aics.example.com:8445'
const [EMAIL,PW]=fs.readFileSync('./.demo_user','utf8').trim().split(' / ')
const OUT=new URL('./shots2/',import.meta.url)
const IDS=['dashboard','cockpit','risiken','bericht']
const b=await firefox.launch(); const c=await b.newContext({ignoreHTTPSErrors:true,viewport:{width:1440,height:1000}}); const p=await c.newPage()
await p.goto(BASE+'/login',{waitUntil:'networkidle'}).catch(()=>{})
await p.getByPlaceholder(/benutzer@|@unternehmen|e-?mail/i).first().fill(EMAIL).catch(async()=>{await p.locator('input[type=email]').first().fill(EMAIL)})
await p.locator('input[type=password]').first().fill(PW)
await p.getByRole('button',{name:/^\s*Anmelden/i}).first().click().catch(()=>p.locator('button[type=submit]').first().click())
await p.waitForTimeout(2500)
await p.evaluate(()=>{history.pushState({},'','/risikobewertung');window.dispatchEvent(new PopStateEvent('popstate'))})
await p.waitForTimeout(2000)
await p.getByText('Demo Risikobewertung',{exact:true}).first().click({force:true}).catch(()=>{})
await p.waitForTimeout(2000)
const texts=await p.locator('.tab-btn').allInnerTexts().catch(()=>[])
console.log('tab-btn texts:', JSON.stringify(texts))
const n=await p.locator('.tab-btn').count()
let ok=0
for(let i=0;i<Math.min(n,IDS.length);i++){
  await p.locator('.tab-btn').nth(i).click({force:true}).catch(()=>{})
  await p.waitForTimeout(1600)
  await p.screenshot({path:new URL(`./risikobewertung__${IDS[i]}.png`,OUT).pathname,fullPage:true})
  ok++
}
console.log('risiko OK', ok)
await b.close()
