// Ergänzt das Wiki um Installation/Updates (öffentliches Repo) + Admin-Logs + Wazuh-Anbindung.
import fs from 'node:fs'
const BASE='http://aics.example.com:6875'
const TOKEN=fs.readFileSync(new URL('./.bs_token',import.meta.url),'utf8').trim()
const H={Authorization:'Token '+TOKEN}
const api=async(m,ep,b)=>{const r=await fetch(BASE+ep,{method:m,headers:{...H,'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});const t=await r.text();if(!r.ok)throw new Error(`${m} ${ep} ${r.status} ${t.slice(0,150)}`);return t?JSON.parse(t):{}}
const upload=async(pageId,file)=>{for(const dir of ['shots2','shots']){const fp=new URL(`./${dir}/${file}`,import.meta.url).pathname;if(!fs.existsSync(fp))continue;const fd=new FormData();fd.set('type','gallery');fd.set('uploaded_to',String(pageId));fd.set('image',new Blob([fs.readFileSync(fp)],{type:'image/png'}),file);const r=await fetch(BASE+'/api/image-gallery',{method:'POST',headers:H,body:fd});if(r.ok)return (await r.json()).url}return null}
async function addPage(bookId,name,md,img){const p=await api('POST','/api/pages',{book_id:bookId,name,markdown:'_(wird befüllt)_'});let body=md;if(img){const u=await upload(p.id,img);body+=u?`\n\n![${name}](${u})`:''}await api('PUT',`/api/pages/${p.id}`,{name,markdown:body});console.log('  +',name)}

const INSTALL=[
['01 · Voraussetzungen & Überblick',`# Installation & Updates — Überblick

Die Suite wird als **Docker-Compose-Stack** betrieben und nutzt die **öffentlichen Container-Images** aus dem öffentlichen Repository **[\`martinzeifang/aics-public\`](https://github.com/martinzeifang/aics-public)** (Images über die GitHub Container Registry) — **es muss nichts aus dem Quellcode gebaut werden**:

- \`ghcr.io/martinzeifang/ai_compliance_suite\` (Anwendung, Web/Backend)
- \`ghcr.io/martinzeifang/aics-nginx\` (Reverse-Proxy, HTTPS)

**Komponenten des Stacks:** \`web\` (App), \`nginx\` (HTTPS-Terminierung), \`postgres\` (Datenbank), \`gotenberg\` (DOCX→PDF), optional \`ollama\` (lokale KI).

**Voraussetzungen:** Docker + Docker Compose v2; ~4 GB RAM (mehr für lokale KI); offener HTTPS-Port (Default 8443).`,null],
['02 · Installation (Docker, öffentliche Images)',`# Installation (Schritt für Schritt)

> Es werden ausschließlich die **öffentlichen Images** verwendet (\`docker compose pull\`), kein lokaler Build.

1. **Compose-Datei + Beispiel-\`.env\` aus dem öffentlichen Repo \`martinzeifang/aics-public\` beziehen** (in ein leeres Verzeichnis):
\`\`\`bash
curl -O https://raw.githubusercontent.com/martinzeifang/aics-public/main/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/martinzeifang/aics-public/main/.env.example
\`\`\`
*(Alternativ das Repo klonen: \`git clone https://github.com/martinzeifang/aics-public.git\`)*
2. **\`.env\` anpassen** (wichtigste Werte; vollständige Liste in \`.env.example\`):
\`\`\`env
AICS_IMAGE_TAG=v6.16.0        # feste Version (empfohlen) oder 'latest'
AICS_HTTPS_PORT=8443
JWT_SECRET_KEY=                # leer = wird beim Erststart generiert
CORS_ORIGINS=https://<host>:8443
ENABLE_DEMO_USERS=false       # Produktion: aus
GUNICORN_WORKERS=4
# optional: AI_CLOUD_API_KEY=…  OLLAMA_DEFAULT_MODEL=llama3.1:8b  LDAP_ENABLED=…  GH_TOKEN=…
\`\`\`
3. **Images ziehen:** \`docker compose pull\`
4. **Starten:** \`docker compose up -d\`
5. **Aufrufen:** \`https://<host>:8443\`
6. **Initial-Admin:** Beim ersten Start (leere DB) wird ein Admin angelegt; die Zugangsdaten stehen im Container unter \`data/db/INITIAL_ADMIN_CREDENTIALS.txt\` (bzw. via \`INITIAL_ADMIN_EMAIL\`). **Nach dem ersten Login Passwort ändern.**`,null],
['03 · Erststart & erste Anmeldung',`# Erststart & erste Anmeldung

1. Mit dem Initial-Admin anmelden (siehe Installation) und **Passwort ändern**.
2. Unter **Administration → Lizenz** die gebuchten Module freischalten (Firmen ist immer verfügbar).
3. Unter **Administration → Einstellungen** den **KI-Provider** wählen (lokale LLM/Ollama oder Cloud).
4. Erste **Firma** anlegen und ein Modul-Projekt starten.`,'login.png'],
['04 · Updates (öffentliche Images)',`# Updates

Updates erfolgen über die **öffentlichen Images** — kein Build:

1. **Vor dem Update:** Backup erstellen (**Administration → Backup**).
2. Gewünschte Version in \`.env\` setzen (\`AICS_IMAGE_TAG=v6.16.0\`) **oder** \`latest\`.
3. **Neue Images ziehen:** \`docker compose pull\`
4. **Neu starten:** \`docker compose up -d\` (rollt \`web\`/\`nginx\` neu aus; Daten bleiben im Volume \`aics_data\`).
5. **Prüfen:** \`https://<host>:8443\` erreichbar, \`docker inspect <container> --format '{{.State.Health.Status}}'\` = \`healthy\`.

**Alternative (automatisiert):** \`docker run --rm -v /var/run/docker.sock:/var/run/docker.sock containrrr/watchtower --run-once --cleanup\` aktualisiert die laufenden Container auf das neueste öffentliche Image.

**Rollback:** in \`.env\` das vorherige \`AICS_IMAGE_TAG\` setzen und \`docker compose up -d\`.`,null],
]

const ADMIN_EXTRA=[
['14 · Logs & Monitoring',`# Logs & Monitoring

**1. In-App Audit-Log (Administration → Audit):** revisionssicheres Protokoll sicherheits-/compliance-relevanter Aktionen (Anmeldungen, Freigaben, Exporte, Löschungen) mit **Akteur, IP-Adresse und Zeit**; filterbar nach Modul/Aktion/Benutzer/Zeitraum. Grundlage für Nachweis-/Rechenschaftspflichten (z. B. DSGVO Art. 5(2)).

**2. Anwendungs-/Container-Logs:**
- \`docker logs aics_web\` — Anwendung/Gunicorn (Fehler, KI-/DB-Meldungen).
- \`docker logs aics_nginx\` — Zugriff/Proxy/TLS.
- Persistentes Volume \`aics_logs\` (\`/app/logs\`).
- Health-Endpoint: \`GET /health\`; Container-Status via \`docker inspect … {{.State.Health.Status}}\`.

**Was zu beachten ist:**
- Bei Problemen **zuerst \`aics_web\`-Logs** prüfen (Detailfehler stehen nur im Server-Log, nicht in der API-Antwort).
- **Keine Geheimnisse in Logs:** API-Keys werden nie ausgegeben; Fehlermeldungen sind bereinigt.
- Audit-Daten gemäß Aufbewahrungspflichten sichern (Backups); Audit ist read-only.`,'admin-audit.png'],
['15 · Wazuh-Anbindung (SOC)',`# Wazuh-Anbindung (SOC)

Das SOC-Modul zieht Sicherheitsalarme aus **Wazuh**. Die Verbindung wird im SOC-Tab **„⚙️ Einrichtung"** angelegt.

**Verbindung konfigurieren:**
- **Modus:** \`pull\` (empfohlen) — read-only vom **Wazuh-Indexer** (OpenSearch, Port **9200**). (Alternativ \`push\`.)
- **URL:** z. B. \`https://<wazuh-indexer>:9200\`
- **Benutzer / Passwort:** ein **read-only Indexer-Konto**.
- **Index-Muster:** \`wazuh-alerts-*\` (Default).
- **Mindest-Level:** Default \`7\` (nur relevante Alarme ziehen).
- **TLS prüfen (\`verify_tls\`):** bei self-signed Zertifikat des Indexers ggf. deaktivieren.
- Mit **„Verbindung testen"** prüfen, anschließend speichern.

**Was zu beachten ist:**
- Port **9200** muss vom Suite-Host zum Indexer erreichbar sein (Netz/Firewall).
- Nur ein **lesendes** Konto verwenden (Least Privilege).
- Danach erscheinen Alarme im Tab **„🚨 Alarme"** (Triage, MITRE-ATT&CK, Eskalation zu Incident); agentenlose Asset-/Log-Quellen-Discovery nutzt denselben Indexer.`,'soc__setup.png'],
]

const run=async()=>{
  const books=(await api('GET','/api/books?count=200')).data||[]
  // Buch "0 · Installation & Updates"
  let inst=books.find(b=>/Installation & Updates/.test(b.name))
  if(!inst) inst=await api('POST','/api/books',{name:'0 · Installation & Updates',description:'Installation und Updates über die öffentlichen Container-Images.'})
  const instPages=(await api('GET',`/api/books/${inst.id}`)).contents||[]
  for(const [n,md,img] of INSTALL){ if(!instPages.find(p=>p.type==='page'&&p.name===n)) await addPage(inst.id,n,md,img); else console.log('  =',n,'(existiert)') }
  console.log('Installation-Buch fertig:',inst.id)
  // Admin-Buch erweitern
  const adminB=books.find(b=>/Einstellungen & Administration/.test(b.name))
  if(adminB){
    const ap=(await api('GET',`/api/books/${adminB.id}`)).contents||[]
    for(const [n,md,img] of ADMIN_EXTRA){ if(!ap.find(p=>p.type==='page'&&p.name===n)) await addPage(adminB.id,n,md,img); else console.log('  =',n,'(existiert)') }
    console.log('Admin-Buch erweitert:',adminB.id)
  } else console.log('Admin-Buch nicht gefunden')
  // Shelf-Reihenfolge: Installation nach vorne
  const shelves=(await api('GET','/api/shelves')).data||[]
  const shelf=shelves.find(s=>/Benutzerhandbuch/.test(s.name))
  if(shelf){
    const detail=await api('GET',`/api/shelves/${shelf.id}`)
    const ids=(detail.books||[]).map(b=>b.id)
    const order=[inst.id,...ids.filter(i=>i!==inst.id)]
    await api('PUT',`/api/shelves/${shelf.id}`,{books:order})
    console.log('Shelf-Reihenfolge gesetzt')
  }
  console.log('DONE')
}
run().catch(e=>{console.error('ERR',e);process.exit(1)})
