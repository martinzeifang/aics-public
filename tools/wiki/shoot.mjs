// #1426 — Screenshot-Pipeline: Playwright + Firefox gegen die Demo (self-signed TLS).
// Echtes Formular-Login (setzt token UND user → Guard ok), dann SPA-Navigation.
import { firefox } from 'playwright'
import fs from 'node:fs'

const BASE = 'https://aics.example.com:8445'
const creds = fs.readFileSync(new URL('./.demo_user', import.meta.url), 'utf8').trim()
const EMAIL = creds.split(' / ')[0]
const PW = creds.split(' / ')[1]
const OUT = new URL('./shots/', import.meta.url)
fs.mkdirSync(OUT, { recursive: true })

const DEFAULT = [
  'home:/', 'firmen:/firmen', 'cra:/cra', 'nis2:/nis2', 'aiact:/aiact',
  'dsgvo:/dsgvo', 'dora:/dora', 'wiba:/wiba', 'soc:/soc',
  'risikobewertung:/risikobewertung', 'admin-settings:/admin/settings',
  'admin-ollama:/admin/ollama', 'admin-templates:/admin/templates',
]
const targets = (process.argv.slice(2).length ? process.argv.slice(2) : DEFAULT)
  .map(s => { const i = s.indexOf(':'); return { name: s.slice(0, i), route: s.slice(i + 1) } })

const shot = async (page, name, ms = 2200) => {
  await page.waitForTimeout(ms)
  await page.screenshot({ path: new URL(`./${name}.png`, OUT).pathname, fullPage: true })
  console.log('SHOT', name)
}

const run = async () => {
  const browser = await firefox.launch()
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()

  await page.goto(BASE + '/login', { waitUntil: 'networkidle', timeout: 45000 }).catch(() => {})
  await shot(page, 'login', 1500)

  // E-Mail + Passwort füllen
  await page.getByPlaceholder(/benutzer@|@unternehmen|e-?mail/i).first().fill(EMAIL).catch(async () => {
    await page.locator('input[type=email]').first().fill(EMAIL)
  })
  await page.locator('input[type=password]').first().fill(PW)

  // GENAU den Submit-Button (nicht den Passkey-Button) — exakter Namensanfang.
  const respP = page.waitForResponse(r => r.url().includes('/api/auth/login'), { timeout: 30000 }).catch(() => null)
  await page.getByRole('button', { name: /^\s*Anmelden/i }).first().click()
    .catch(() => page.locator('button[type=submit]').first().click())
  const resp = await respP
  console.log('login response:', resp ? resp.status() : 'KEINE')
  await page.waitForTimeout(3000)
  console.log('URL nach Login:', page.url())

  // Client-seitige SPA-Navigation (kein Reload → User bleibt im Store, Guard ok)
  for (const t of targets) {
    try {
      await page.evaluate((path) => {
        history.pushState({}, '', path)
        window.dispatchEvent(new PopStateEvent('popstate'))
      }, t.route)
      await page.waitForLoadState('networkidle').catch(() => {})
      await page.waitForTimeout(500)
      const url = page.url()
      if (url.endsWith('/login')) { console.log('BOUNCED', t.name); continue }
      await shot(page, t.name)
    } catch (e) {
      console.log('FAIL', t.name, String(e).slice(0, 120))
    }
  }
  await browser.close()
}
run().then(() => console.log('DONE')).catch(e => { console.error('ERR', e); process.exit(1) })
