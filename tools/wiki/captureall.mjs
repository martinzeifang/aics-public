// Vollständige Tab-Screenshots: pro Modul Projekt öffnen, jede Gruppe+jeden Tab.
import { firefox } from 'playwright'
import fs from 'node:fs'
import { MOD_TABS } from './tabs.mjs'

const BASE = 'https://aics.example.com:8445'
const creds = fs.readFileSync(new URL('./.demo_user', import.meta.url), 'utf8').trim()
const [EMAIL, PW] = creds.split(' / ')
const OUT = new URL('./shots2/', import.meta.url)
fs.mkdirSync(OUT, { recursive: true })
const esc = s => s.replace(/[.*+?^${}()|[\]\\\/]/g, '\\$&')
const only = process.argv.slice(2) // optional: nur diese Module

const run = async () => {
  const browser = await firefox.launch()
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 1000 } })
  const page = await ctx.newPage()
  await page.goto(BASE + '/login', { waitUntil: 'networkidle' }).catch(() => {})
  await page.getByPlaceholder(/benutzer@|@unternehmen|e-?mail/i).first().fill(EMAIL).catch(async () => { await page.locator('input[type=email]').first().fill(EMAIL) })
  await page.locator('input[type=password]').first().fill(PW)
  await page.getByRole('button', { name: /^\s*Anmelden/i }).first().click().catch(() => page.locator('button[type=submit]').first().click())
  await page.waitForTimeout(3000)

  const nav = async route => {
    await page.evaluate(p => { history.pushState({}, '', p); window.dispatchEvent(new PopStateEvent('popstate')) }, route)
    await page.waitForLoadState('networkidle').catch(() => {})
    await page.waitForTimeout(900)
  }
  const shot = async (name, ms = 1400) => { await page.waitForTimeout(ms); await page.screenshot({ path: new URL(`./${name}.png`, OUT).pathname, fullPage: true }) }

  const mods = Object.keys(MOD_TABS).filter(m => !only.length || only.includes(m))
  const report = {}
  for (const mod of mods) {
    report[mod] = { ok: [], miss: [] }
    await nav('/' + mod)
    await page.waitForTimeout(800)
    // Projekt öffnen — Leaf-Texte "Demo …" sammeln, exakt + force klicken
    const names = await page.evaluate(() => {
      const out = []
      document.querySelectorAll('*').forEach(el => {
        if (el.children.length === 0) {
          const t = (el.textContent || '').trim()
          if (/^Demo[\s-]/.test(t) && t.length < 40) out.push(t)
        }
      })
      return [...new Set(out)]
    }).catch(() => [])
    for (const name of names) {
      await page.getByText(name, { exact: true }).first().click({ force: true }).catch(() => {})
      await page.waitForTimeout(1200)
      if (await page.locator('.nav-tab, .nav-group').count().catch(() => 0) > 0) break
    }
    const groupCount = await page.locator('.nav-group').count().catch(() => 0)
    if (await page.locator('.nav-tab,.nav-group,.tab-btn').count().catch(() => 0) === 0) {
      console.log(mod, '— kein Projekt/Nav geöffnet'); continue
    }
    for (const [id, label] of MOD_TABS[mod]) {
      const rx = new RegExp('^\\s*' + esc(label) + '\\s*$')
      let done = false
      const tryClick = async () => {
        const t = page.locator('.nav-tab, .tab-btn').filter({ hasText: rx }).first()
        if (await t.count().catch(() => 0) && await t.isVisible().catch(() => false)) {
          await t.click({ force: true }).catch(() => {}); return true
        }
        return false
      }
      if (await tryClick()) done = true
      else {
        for (let gi = 0; gi < groupCount; gi++) {
          await page.locator('.nav-group').nth(gi).click({ force: true }).catch(() => {})
          await page.waitForTimeout(250)
          if (await tryClick()) { done = true; break }
        }
      }
      if (done) { await shot(`${mod}__${id}`); report[mod].ok.push(id) }
      else { report[mod].miss.push(id) }
    }
    console.log(mod, 'OK', report[mod].ok.length, 'MISS', report[mod].miss.length, report[mod].miss.join(',') || '')
  }
  await browser.close()
  console.log('DONE')
}
run().catch(e => { console.error('ERR', e); process.exit(1) })
