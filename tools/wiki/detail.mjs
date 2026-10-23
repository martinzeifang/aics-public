// Detail-Screenshots: Projekt öffnen + Tabs. Aufruf: node detail.mjs
import { firefox } from 'playwright'
import fs from 'node:fs'
const BASE = 'https://aics.example.com:8445'
const creds = fs.readFileSync(new URL('./.demo_user', import.meta.url), 'utf8').trim()
const [EMAIL, PW] = creds.split(' / ')
const OUT = new URL('./shots/', import.meta.url)

const shot = async (page, name, ms = 2200) => {
  await page.waitForTimeout(ms)
  await page.screenshot({ path: new URL(`./${name}.png`, OUT).pathname, fullPage: true })
  console.log('SHOT', name)
}
const nav = async (page, route) => {
  await page.evaluate(p => { history.pushState({}, '', p); window.dispatchEvent(new PopStateEvent('popstate')) }, route)
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.waitForTimeout(800)
}

const run = async () => {
  const browser = await firefox.launch()
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' }).catch(() => {})
  await page.getByPlaceholder(/benutzer@|@unternehmen|e-?mail/i).first().fill(EMAIL).catch(async () => { await page.locator('input[type=email]').first().fill(EMAIL) })
  await page.locator('input[type=password]').first().fill(PW)
  await page.getByRole('button', { name: /^\s*Anmelden/i }).first().click().catch(() => page.locator('button[type=submit]').first().click())
  await page.waitForTimeout(3000)

  // module -> [tab labels to click after opening project]
  const MODS = {
    cra: ['Dashboard', 'Anforderungen', 'Pflicht-Doku', 'Dokumente', 'Berichte'],
    nis2: ['Dashboard', 'Anforderungen', 'Assistenten', 'Dokumente'],
    aiact: ['Dashboard', 'Anforderungen', 'Assistenten'],
    dsgvo: ['Dashboard', 'VVT', 'TOM', 'Dokumente'],
    dora: ['Dashboard', 'Anforderungen'],
    wiba: ['Prüffragen', 'Dokumente'],
    risikobewertung: [],
  }
  for (const [mod, tabs] of Object.entries(MODS)) {
    try {
      await nav(page, '/' + mod)
      // erstes Projekt in der linken Spalte öffnen (Text beginnt mit "Demo")
      const proj = page.getByText(/^Demo/).first()
      if (await proj.count().catch(() => 0)) {
        await proj.click({ timeout: 5000 }).catch(() => {})
        await page.waitForTimeout(1500)
      }
      await shot(page, mod + '-detail')
      for (const tab of tabs) {
        const el = page.getByRole('tab', { name: new RegExp(tab, 'i') }).first()
        let clicked = await el.click({ timeout: 3000 }).then(() => true).catch(() => false)
        if (!clicked) clicked = await page.getByRole('button', { name: new RegExp('^' + tab, 'i') }).first().click({ timeout: 2500 }).then(() => true).catch(() => false)
        if (!clicked) clicked = await page.locator('button, a, [role=tab]').filter({ hasText: new RegExp('^\\s*' + tab, 'i') }).first().click({ timeout: 2500 }).then(() => true).catch(() => false)
        if (clicked) { await shot(page, `${mod}-${tab.toLowerCase().replace(/[^a-z0-9]+/g, '')}`, 1800) }
      }
    } catch (e) { console.log('FAIL', mod, String(e).slice(0, 100)) }
  }
  await browser.close()
}
run().then(() => console.log('DONE')).catch(e => { console.error('ERR', e); process.exit(1) })
