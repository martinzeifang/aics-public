// Publiziert je Modul-Buch: Überblick (bleibt) + eine Seite pro Tab/Funktion.
import fs from 'node:fs'
import { MOD_TABS } from './tabs.mjs'
import { MODULE_BOOK, DESC, cleanTitle } from './content2.mjs'

const BASE = 'http://aics.example.com:6875'
const TOKEN = fs.readFileSync(new URL('./.bs_token', import.meta.url), 'utf8').trim()
const SHOTS2 = new URL('./shots2/', import.meta.url)
const H = { 'Authorization': 'Token ' + TOKEN }

const api = async (method, ep, body) => {
  const r = await fetch(BASE + ep, { method, headers: { ...H, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  const t = await r.text()
  if (!r.ok) throw new Error(`${method} ${ep} -> ${r.status} ${t.slice(0, 150)}`)
  return t ? JSON.parse(t) : {}
}
const uploadImage = async (pageId, file) => {
  const fp = new URL('./' + file, SHOTS2).pathname
  if (!fs.existsSync(fp)) return null
  const fd = new FormData()
  fd.set('type', 'gallery'); fd.set('uploaded_to', String(pageId))
  fd.set('image', new Blob([fs.readFileSync(fp)], { type: 'image/png' }), file)
  const r = await fetch(BASE + '/api/image-gallery', { method: 'POST', headers: H, body: fd })
  return r.ok ? (await r.json()).url : null
}
const pad = n => String(n).padStart(2, '0')

const run = async () => {
  const books = (await api('GET', '/api/books?count=200')).data || []
  for (const [mod, bookName] of Object.entries(MODULE_BOOK)) {
    const book = books.find(b => b.name === bookName)
    if (!book) { console.log('Buch fehlt:', bookName); continue }
    const detail = await api('GET', `/api/books/${book.id}`)
    const pages = (detail.contents || []).filter(c => c.type === 'page')
    // Aufräumen: alle Seiten außer "Überblick" löschen (idempotenter Neuaufbau)
    for (const pg of pages) {
      if (pg.name !== 'Überblick') { await api('DELETE', `/api/pages/${pg.id}`).catch(() => {}) }
    }
    console.log(`\n${bookName} (id ${book.id}) — ${MOD_TABS[mod].length} Funktionen`)
    let i = 0
    for (const [id, label] of MOD_TABS[mod]) {
      i++
      const title = `${pad(i)} · ${cleanTitle(label)}`
      const desc = (DESC[mod] && DESC[mod][id]) || '_(Beschreibung folgt.)_'
      const imgFile = `${mod}__${id}.png`
      const page = await api('POST', '/api/pages', { book_id: book.id, name: title, markdown: '_(wird befüllt)_' })
      const url = await uploadImage(page.id, imgFile)
      const imgMd = url ? `\n\n![${cleanTitle(label)}](${url})` : '\n\n_(Screenshot folgt.)_'
      const md = `# ${cleanTitle(label)}\n\n${desc}${imgMd}`
      await api('PUT', `/api/pages/${page.id}`, { name: title, markdown: md })
      console.log('  +', title, url ? '🖼' : '∅')
    }
  }
  console.log('\nDONE')
}
run().catch(e => { console.error('ERR', e); process.exit(1) })
