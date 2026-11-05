// Publiziert die Benutzer-Doku nach BookStack (REST API).
// Bilder: pro Seite hochladen (uploaded_to=page_id), {{img:datei}} → URL ersetzen.
import fs from 'node:fs'
import path from 'node:path'
import { BOOKS, SHELF } from './content.mjs'

const BASE = 'http://aics.example.com:6875'
const TOKEN = fs.readFileSync(new URL('./.bs_token', import.meta.url), 'utf8').trim()
const SHOTS = new URL('./shots/', import.meta.url)
const H = { 'Authorization': 'Token ' + TOKEN }

const api = async (method, ep, body) => {
  const r = await fetch(BASE + ep, { method, headers: { ...H, 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  const txt = await r.text()
  if (!r.ok) throw new Error(`${method} ${ep} -> ${r.status} ${txt.slice(0, 200)}`)
  return txt ? JSON.parse(txt) : {}
}

const uploadImage = async (pageId, file) => {
  const fp = new URL('./' + file, SHOTS).pathname
  if (!fs.existsSync(fp)) { console.log('  (img fehlt, übersprungen):', file); return null }
  const fd = new FormData()
  fd.set('type', 'gallery')
  fd.set('uploaded_to', String(pageId))
  fd.set('image', new Blob([fs.readFileSync(fp)], { type: 'image/png' }), file)
  const r = await fetch(BASE + '/api/image-gallery', { method: 'POST', headers: H, body: fd })
  if (!r.ok) { console.log('  img upload fail', file, r.status, (await r.text()).slice(0,120)); return null }
  return (await r.json()).url
}

const run = async () => {
  // Shelf finden/anlegen
  const shelves = (await api('GET', '/api/shelves')).data || []
  let shelf = shelves.find(s => s.name === SHELF.name)
  if (!shelf) shelf = await api('POST', '/api/shelves', { name: SHELF.name, description: SHELF.description })
  console.log('Shelf:', shelf.id, shelf.name)

  const existingBooks = (await api('GET', '/api/books?count=200')).data || []
  const bookIds = []
  for (const b of BOOKS) {
    let book = existingBooks.find(x => x.name === b.name)
    if (!book) book = await api('POST', '/api/books', { name: b.name, description: b.description })
    bookIds.push(book.id)
    console.log('Book:', book.id, book.name)
    // existierende Seiten des Buchs (idempotent: per Name updaten)
    const pages = (await api('GET', `/api/books/${book.id}`)).contents || []
    for (const pg of b.pages) {
      let page = pages.find(p => p.type === 'page' && p.name === pg.name)
      if (!page) {
        page = await api('POST', '/api/pages', { book_id: book.id, name: pg.name, markdown: '_(wird befüllt)_' })
      }
      let md = pg.md
      // {{img:datei.png}}-Tokens direkt aus dem Markdown extrahieren + hochladen
      const files = [...new Set([...md.matchAll(/\{\{img:([^}]+)\}\}/g)].map(m => m[1].trim()))]
      for (const file of files) {
        const url = await uploadImage(page.id, file)
        const token = `{{img:${file}}}`
        md = url ? md.replaceAll(token, `![${file}](${url})`)
                 : md.replaceAll(token, `_(Screenshot ${file} folgt)_`)
      }
      await api('PUT', `/api/pages/${page.id}`, { name: pg.name, markdown: md })
      console.log('  Page:', page.id, pg.name)
    }
  }
  // Bücher dem Shelf zuordnen
  await api('PUT', `/api/shelves/${shelf.id}`, { books: bookIds })
  console.log('DONE — Shelf-Books:', bookIds.length)
}
run().catch(e => { console.error('ERR', e); process.exit(1) })
