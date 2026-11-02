<template>
  <div class="admin-settings">
    <header class="page-header">
      <h1>⚙️ Einstellungen</h1>
      <p class="muted">Jede Option als eigene Kachel — wähle einen Bereich.</p>
    </header>

    <!-- KI-Provider-Status (Sprint #16, #877): read-only Transparenz Lokal/Cloud + Egress -->
    <div class="ki-status-card">
      <div class="ki-status-head">
        <h2>🤖 Aktiver KI-Provider</h2>
        <AIProviderBadge />
      </div>
      <p class="muted">Aktueller Provider und Daten-Egress-Status (read-only).</p>
      <dl v-if="kiStatus" class="ki-dl">
        <div class="ki-dl-row">
          <dt>Provider</dt>
          <dd>{{ kiStatus.label }} <span class="ki-mono">({{ kiStatus.provider }})</span></dd>
        </div>
        <div class="ki-dl-row">
          <dt>Status</dt>
          <dd>{{ kiStatus.configured ? 'konfiguriert' : 'nicht konfiguriert' }}</dd>
        </div>
        <div class="ki-dl-row">
          <dt>Daten-Egress</dt>
          <dd :class="{ 'ki-warn': kiStatus.allow_data_egress }">
            {{ kiStatus.allow_data_egress
              ? '⚠️ erlaubt — Daten können dein Netzwerk verlassen'
              : 'blockiert — Daten bleiben lokal' }}
          </dd>
        </div>
      </dl>
      <p v-else-if="kiError" class="err">KI-Provider-Status konnte nicht geladen werden.</p>
      <p class="muted ki-help">
        Mehr dazu:
        <a href="/docs/ki-funktionen/" target="_blank" rel="noopener">
          Wie funktionieren die KI-Funktionen?</a>
      </p>
    </div>

    <!-- Kachel-Grid: eine Kachel pro Option -->
    <div class="tile-grid">
      <button v-for="t in tiles" :key="t.key" class="settings-tile" @click="openTile(t.key)">
        <span class="tile-icon">{{ t.icon }}</span>
        <span class="tile-title">{{ t.title }}</span>
        <span class="tile-desc">{{ t.desc }}</span>
      </button>
    </div>

    <!-- SettingsDialog (fokussiert) für ai/github/modules/appearance/backup -->
    <SettingsDialog v-if="dialogOnly" :open="true" :only="dialogOnly" @close="dialogOnly = null" />

    <!-- Passkey / WebAuthn -->
    <div v-if="panel === 'passkey'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>🔑 Passkey / WebAuthn</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">
            Damit Passkeys funktionieren, müssen RP-ID und Origin zur aufgerufenen URL passen.
            <strong>RP-ID = vollständiger Hostname (keine IP, kein Schema/Port).</strong>
          </p>
          <div v-if="waLoading" class="muted">Lade Konfiguration…</div>
          <template v-else>
            <div class="btn-row" style="margin-bottom:8px;">
              <button class="btn-secondary" @click="loadWebauthnSuggest" :disabled="waSaving">🔎 Vorschlag laden (erkannter Host)</button>
            </div>
            <div class="form-row">
              <label>RP-ID (vollständiger Hostname)</label>
              <input v-model="waConfig.rp_id" placeholder="z.B. compliancesuite.c99781.intern" />
              <small v-if="rpIdHint" class="err">⚠ {{ rpIdHint }}</small>
              <small v-else class="muted" style="font-size:12px;">Muss der volle Hostname der aufgerufenen URL sein (oder ein registrierbares Suffix).</small>
            </div>
            <div class="form-row">
              <label>RP-Name</label>
              <input v-model="waConfig.rp_name" placeholder="AI Compliance Suite" />
            </div>
            <div class="form-row">
              <label>Origin(s) — komma-separiert</label>
              <input v-model="waConfig.rp_origin" placeholder="https://compliancesuite.c99781.intern:8443" />
            </div>
            <p class="muted" style="font-size:12px;">
              Quelle aktuell: {{ waConfig.from_settings ? 'Web-Einstellungen' : 'ENV/Default (noch nicht über Web gesetzt)' }}
            </p>
            <div class="btn-row">
              <button class="btn-primary" @click="saveWebauthn" :disabled="waSaving || !!rpIdHint">
                {{ waSaving ? 'Speichert…' : 'Speichern' }}
              </button>
              <span v-if="waSavedMsg" class="ok">{{ waSavedMsg }}</span>
              <span v-if="waError" class="err">⚠ {{ waError }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- MFA-Richtlinie -->
    <div v-if="panel === 'mfa'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>🛡️ MFA-Richtlinie</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">Mehr-Faktor-Authentifizierung (TOTP oder Passkey) ist für alle Benutzer verfügbar. Hier legen Sie fest, ob sie verpflichtend ist.</p>
          <div v-if="mfaLoading" class="muted">Lade Richtlinie…</div>
          <template v-else>
            <div class="form-row">
              <label>Modus</label>
              <select v-model="mfaPolicy.mode">
                <option value="optional">Optional — jeder kann MFA selbst aktivieren</option>
                <option value="required_all">Pflicht für alle Benutzer</option>
                <option value="required_roles">Pflicht für bestimmte Rollen</option>
              </select>
            </div>
            <div v-if="mfaPolicy.mode === 'required_roles'" class="form-row">
              <label>Betroffene Rollen</label>
              <div class="role-checks">
                <label v-for="r in knownRoles" :key="r" class="role-check">
                  <input type="checkbox" :value="r" :checked="mfaPolicy.required_roles.includes(r)" @change="toggleRole(r, $event)" />
                  {{ r }}
                </label>
              </div>
            </div>
            <div v-if="mfaPolicy.mode !== 'optional'" class="form-row">
              <label>Übergangsfrist (Tage bis Einrichtung erzwungen wird)</label>
              <input type="number" min="0" max="90" v-model.number="mfaPolicy.grace_days" />
            </div>
            <div class="btn-row">
              <button class="btn-primary" @click="saveMfaPolicy" :disabled="mfaSaving">
                {{ mfaSaving ? 'Speichert…' : 'Richtlinie speichern' }}
              </button>
              <span v-if="mfaSavedMsg" class="ok">{{ mfaSavedMsg }}</span>
              <span v-if="mfaError" class="err">⚠ {{ mfaError }}</span>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Zertifikate -->
    <div v-if="panel === 'certs'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>📜 Zertifikate (TLS)</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">
            Self-Signed-Zertifikat für Hostname/IP, Zertifikatsantrag (CSR) für eure PKI,
            und Verwaltung aller gespeicherten Zertifikate.
          </p>
          <div v-if="certCurrent" class="cert-current">
            <strong>Aktives Zertifikat:</strong>
            <span v-if="certCurrent.present">
              {{ certCurrent.common_name || '—' }}
              <span class="muted">· gültig bis {{ (certCurrent.not_after || '').slice(0,10) }}</span>
            </span>
            <span v-else class="muted">keines gefunden</span>
          </div>
          <div class="btn-row">
            <button class="btn-primary" @click="showManager = true">🗂 Zertifikate verwalten</button>
            <button class="btn-secondary" @click="showSelfSigned = true">＋ Self-Signed</button>
            <button class="btn-secondary" @click="showCsr = true">📜 CSR für PKI</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Version & Updates (#1512) -->
    <div v-if="panel === 'updates'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>⬆️ Version & Updates</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <div class="upd-row">
            <span class="upd-label">Installierte Version:</span>
            <code>{{ admin.versionInfo?.current || '…' }}</code>
            <template v-if="admin.versionInfo">
              <span v-if="admin.versionInfo.update_available === true" class="badge badge-warn">
                Update verfügbar: {{ admin.versionInfo.latest }}
              </span>
              <span v-else-if="admin.versionInfo.update_available === false" class="badge badge-ok">✓ aktuell</span>
              <span v-else class="badge badge-muted">Status unbekannt (offline?)</span>
            </template>
          </div>
          <!-- #1908: Woher dieses Image kommt. Aus Build-Metadaten, also auch
               ohne Portainer und auf jeder Plattform ablesbar. -->
          <div v-if="herkunft?.metadaten_vorhanden" class="upd-row">
            <span class="upd-label">Dieses Image:</span>
            <code v-if="herkunft.image_tag">{{ herkunft.image_tag }}</code>
            <span v-if="herkunft.oeffentlich" class="badge badge-ok">✓ öffentlich gebaut</span>
            <span v-else-if="herkunft.quelle" class="badge badge-warn">
              privat gebaut
            </span>
            <span v-if="herkunft.unveroeffentlicht" class="badge badge-warn">
              ⚠ unveröffentlichter Stand
            </span>
            <span v-else-if="herkunft.vorabfassung" class="badge badge-warn">Vorabfassung</span>
          </div>
          <p v-if="herkunft?.unveroeffentlicht" class="muted small">
            Diese Installation läuft auf einem Entwicklungsstand. Die oben
            angezeigte Version stammt aus dem Quellbaum und bezeichnet
            <strong>nicht</strong> den gebauten Stand — für einen Nachweis ist
            ein Release nötig.
          </p>

          <!-- #1908: Release-Kanal -->
          <div class="kanal">
            <h3>📦 Release-Kanal</h3>
            <label v-for="c in (admin.versionInfo?.channels || [])" :key="c.name" class="kanal-wahl">
              <input type="radio" name="kanal" :value="c.name"
                     :checked="kanalWahl === c.name" @change="kanalWahl = c.name" />
              <span>
                <strong>{{ c.titel }}</strong>
                <span v-if="!c.quelle_geprueft" class="badge badge-warn">ohne Herkunftsprüfung</span>
                <span class="muted small kanal-desc">{{ c.beschreibung }}</span>
              </span>
            </label>
            <div class="btn-row">
              <button class="btn-secondary" @click="onSaveKanal"
                      :disabled="kanalSaving || kanalWahl === admin.versionInfo?.channel">
                {{ kanalSaving ? 'Speichere…' : '💾 Kanal speichern' }}
              </button>
            </div>
            <span v-if="kanalMsg" :class="kanalOk ? 'ok' : 'err'">{{ kanalMsg }}</span>
          </div>

          <div class="btn-row">
            <button class="btn-secondary" @click="onCheckVersion" :disabled="checking">
              {{ checking ? 'Prüfe…' : '🔄 Nach Updates suchen' }}
            </button>
            <button v-if="admin.versionInfo?.update_configured"
                    class="btn-primary" @click="onUpdate" :disabled="updating"
                    title="Nur die beiden AICS-Images werden gezogen; Datenbank,
Konverter und Ollama bleiben unangetastet. Die Container starten neu.">
              {{ updating ? 'Starte Update…' : '⬇️ Update installieren' }}
            </button>
          </div>

          <!-- #1908: Ohne Treiber KEIN Knopf, sondern der Tag und der Befehl.
               Ein sichtbarer Knopf, der nichts tun kann, ist der Fehler aus
               #1805/#1830 — und mit compose, Swarm oder k8s kann die Anwendung
               nichts umstellen. -->
          <div v-if="!admin.versionInfo?.update_configured" class="selbst">
            <p class="muted">
              Für diese Installation ist kein Portainer hinterlegt — die
              Anwendung kann sich nicht selbst umstellen. Sie nennt dir aber den
              Stand, auf den du gehen willst:
            </p>
            <div v-if="admin.versionInfo?.ziel_tag" class="selbst-tag">
              <code>AICS_IMAGE_TAG={{ admin.versionInfo.ziel_tag }}</code>
              <button class="btn-small" @click="onKopiereTag">
                {{ tagKopiert ? '✓ Kopiert' : '📋 Kopieren' }}
              </button>
            </div>
            <p v-else class="muted small">
              Im gewählten Kanal ist keine Zielversion bekannt. Unter
              <em>update.version_check_url</em> eine Quelle hinterlegen oder die
              Version von Hand eintragen.
            </p>
            <details class="selbst-hilfe">
              <summary>Wie trage ich das ein?</summary>
              <p class="muted small"><strong>docker compose:</strong> den Wert in die
                <code>.env</code> des Stacks schreiben, dann
                <code>docker compose pull web nginx &amp;&amp; docker compose up -d</code>.
                Bewusst nur die beiden AICS-Dienste — ein <code>pull</code> ohne
                Dienstnamen zieht auch Datenbank, Konverter und Ollama neu.</p>
              <p class="muted small"><strong>Swarm / Kubernetes:</strong> das Image-Tag
                der beiden AICS-Dienste auf diesen Wert setzen.</p>
              <p class="muted small"><strong>Watchtower:</strong> wirkt nur auf
                bewegliche Tags; für einen festen Stand ist er der falsche Weg.</p>
            </details>
          </div>

          <span v-if="updMsg" class="ok">{{ updMsg }}</span>
          <span v-if="admin.error" class="err">⚠ {{ admin.error }}</span>

          <!-- #1534: Portainer-Zugangsdaten direkt konfigurieren -->
          <div class="portainer-cfg">
            <h3>🔗 Portainer-Zugangsdaten</h3>
            <label class="pf-lbl">Portainer-URL
              <input v-model="pForm.base_url" placeholder="https://docker01:9443" />
            </label>
            <div class="pf-two">
              <label class="pf-lbl">Stack-ID
                <input v-model.number="pForm.stack_id" type="number" placeholder="45" />
              </label>
              <label class="pf-lbl">Endpoint-ID
                <input v-model.number="pForm.endpoint_id" type="number" placeholder="2" />
              </label>
            </div>
            <label class="pf-lbl">API-Key
              <span v-if="pForm.api_key_set" class="pf-hint">— gesetzt · leer lassen = behalten</span>
              <input v-model="pForm.api_key" type="password" autocomplete="new-password" placeholder="ptr_…" />
            </label>
            <label class="pf-chk">
              <input type="checkbox" v-model="pForm.verify_tls" />
              TLS-Zertifikat prüfen <span class="pf-hint">(bei internem self-signed Portainer deaktivieren)</span>
            </label>
            <div class="btn-row">
              <button class="btn-secondary" @click="onSavePortainer" :disabled="pSaving">
                {{ pSaving ? 'Speichere…' : '💾 Speichern' }}
              </button>
              <button class="btn-secondary" @click="onTestPortainer" :disabled="pTesting">
                {{ pTesting ? 'Teste…' : '🔌 Verbindung testen' }}
              </button>
            </div>
            <span v-if="pMsg" :class="pOk ? 'ok' : 'err'">{{ pMsg }}</span>
            <p class="muted pf-note">⚠️ Ein Portainer-<strong>Admin</strong>-Key gibt Vollzugriff auf alle Stacks —
              idealerweise einen auf den Ziel-Stack beschränkten Key verwenden. Der Key wird verschlüsselt gespeichert
              (at-rest). Für ein internes Portainer mit self-signed Zertifikat die TLS-Prüfung deaktivieren.</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Support-Bundle (#1509) -->
    <div v-if="panel === 'support'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>🛟 Support-Bundle</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">
            Erstellt ein ZIP mit allen für die Fehlersuche relevanten Logdateien
            und Diagnose-Infos (App-/Audit-Logs, Versions-/Plattform-Manifest,
            redigierte Konfiguration). Secrets, Passwörter und API-Keys werden
            entfernt. Lade es bei einer Support-Anfrage hoch.
          </p>
          <div class="btn-row">
            <button class="btn-primary" @click="onSupportBundle" :disabled="bundling">
              {{ bundling ? 'Erstelle Bundle…' : '🛟 Support-Bundle herunterladen' }}
            </button>
          </div>
          <span v-if="updMsg" class="ok">{{ updMsg }}</span>
          <span v-if="admin.error" class="err">⚠ {{ admin.error }}</span>
        </div>
      </div>
    </div>

    <!-- Verordnungstexte (#1894) — bis v8.2.3 konnte sie nur der
         Tkinter-Dialog des Gutachten-Moduls holen, den der Administrator einer
         gehosteten Installation nicht hat. Die Fähigkeit war da und nicht
         bedienbar (dieselbe Form wie #1823 und #1878). -->
    <div v-if="panel === 'verordnungen'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>📕 Verordnungstexte</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">
            Mehrere Module zitieren Fundstellen, die in unterschriebene
            Dokumente gedruckt werden — Anhang V der CRA, Anhang V der KI-VO,
            Artikel der DSGVO. Maßgeblich ist die amtliche Fassung im
            Amtsblatt; liegt sie hier, ist jede Angabe am Original nachlesbar.
            Geholt wird über die Publikationsstelle der EU.
          </p>
          <table class="vo-tabelle">
            <thead>
              <tr><th>Rechtsakt</th><th>CELEX</th><th>Stand</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="v in verordnungen" :key="v.schluessel">
                <td>
                  {{ v.titel }}
                  <div class="muted small">{{ v.zitiert_in }}</div>
                  <div class="muted small">{{ v.verzeichnis }}</div>
                </td>
                <td><code>{{ v.celex }}</code></td>
                <td>
                  <span v-if="v.vorhanden" class="ok">✓ liegt vor</span>
                  <span v-else-if="v.nur_fragment" class="err">
                    ⚠ Datei da, aber kein PDF
                  </span>
                  <span v-else class="muted">— fehlt</span>
                </td>
                <td>
                  <button class="btn-small" :disabled="voBusy === v.schluessel"
                          @click="onVerordnungHolen(v.schluessel, v.vorhanden)">
                    {{ voBusy === v.schluessel ? '⏳ …'
                       : (v.vorhanden ? 'Erneut holen' : 'Holen') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="voMsg" class="ok">{{ voMsg }}</p>
          <p v-if="voErr" class="err">⚠ {{ voErr }}</p>
          <p class="muted small">
            Scheitert der Abruf (kein Netz, Gegenstelle antwortet nicht), lege
            das PDF von Hand mit der CELEX-Nummer im Dateinamen in das genannte
            Verzeichnis.
          </p>
        </div>
      </div>
    </div>

    <!-- PDF-Konverter (#1903) — „nicht verfügbar" soll belegbar sein. -->
    <div v-if="panel === 'pdf'" class="hub-overlay" @mousedown.self="panel = null">
      <div class="hub-modal">
        <div class="hub-head"><h2>🖨️ PDF-Konverter</h2><button class="x" @click="panel = null">✕</button></div>
        <div class="hub-body">
          <p class="muted">
            Word-Dokumente werden über einen eigenen Dienst (Gotenberg mit
            LibreOffice) in PDF umgewandelt. Diese Ansicht misst seinen Zustand
            — damit eine Fehlermeldung „nicht erreichbar" belegt ist und nicht
            vermutet.
          </p>
          <table class="vo-tabelle" v-if="pdfStatus">
            <tbody>
              <tr>
                <td>Gesamtzustand</td>
                <td>
                  <span v-if="pdfStatus.bereit" class="ok">✓ bereit</span>
                  <span v-else class="err">⚠ keine PDF-Erzeugung möglich</span>
                </td>
              </tr>
              <tr>
                <td>Dienst erreichbar<div class="muted small">{{ pdfStatus.gotenberg_url }}</div></td>
                <td>
                  <span v-if="pdfStatus.erreichbar" class="ok">✓ ja</span>
                  <span v-else class="err">✗ nein</span>
                </td>
              </tr>
              <tr>
                <td>LibreOffice im Dienst</td>
                <td>
                  <span v-if="pdfStatus.libreoffice === 'up'" class="ok">✓ läuft</span>
                  <span v-else-if="pdfStatus.libreoffice === 'down'" class="err">✗ ausgefallen</span>
                  <span v-else class="muted">— {{ pdfStatus.libreoffice }}</span>
                </td>
              </tr>
              <tr v-if="pdfStatus.version">
                <td>Version</td><td><code>{{ pdfStatus.version }}</code></td>
              </tr>
              <tr>
                <td>
                  Zeitgrenzen
                  <div class="muted small">
                    Der Dienst darf {{ pdfStatus.api_timeout_s }} s arbeiten, die
                    Anwendung wartet {{ pdfStatus.client_timeout_s }} s.
                  </div>
                </td>
                <td>
                  <span v-if="pdfStatus.zeitlimit_ok" class="ok">✓ richtige Reihenfolge</span>
                  <span v-else class="err">
                    ⚠ die Anwendung gibt zuerst auf — dabei können
                    LibreOffice-Prozesse zurückbleiben, die jede weitere
                    Umwandlung scheitern lassen
                  </span>
                </td>
              </tr>
              <tr>
                <td>Lokales LibreOffice<div class="muted small">Rückfall, nur auf Entwicklungsmaschinen</div></td>
                <td>
                  <span v-if="pdfStatus.lokales_soffice" class="ok">✓ vorhanden</span>
                  <span v-else class="muted">— nicht vorhanden</span>
                </td>
              </tr>
              <tr v-if="pdfStatus.meldung">
                <td>Meldung</td><td><code>{{ pdfStatus.meldung }}</code></td>
              </tr>
            </tbody>
          </table>
          <p v-if="pdfErr" class="err">⚠ {{ pdfErr }}</p>
          <button class="btn-small" :disabled="pdfBusy" @click="ladePdfKonverter">
            {{ pdfBusy ? '⏳ …' : 'Erneut prüfen' }}
          </button>
          <p class="muted small">
            Scheitert jede Umwandlung, obwohl hier alles grün ist, hängt meist
            ein LibreOffice-Prozess im Konverter-Container. Nachsehen mit
            <code>docker exec &lt;konverter&gt; ps -o pid,etime,comm</code>; eine
            Laufzeit in Minuten bei <code>soffice.bin</code> ist der Befund, ein
            Neustart des Konverter-Containers behebt es.
          </p>
        </div>
      </div>
    </div>

    <CertManager v-if="showManager" @close="showManager = false" @applied="onCertApplied" />
    <CertSelfSignedWizard v-if="showSelfSigned" @close="showSelfSigned = false" @applied="onCertApplied" />
    <CertCsrWizard v-if="showCsr" @close="showCsr = false" @applied="onCertApplied" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import axios from 'axios'
import SettingsDialog from '../../components/SettingsDialog.vue'
import AIProviderBadge from '../../components/shared/AIProviderBadge.vue'
import { useAiProviderStore } from '../../stores/aiProvider'
import { useAdminStore } from '../../stores/admin'
import { kopiere } from '../../utils/zwischenablage'
import CertSelfSignedWizard from './dialogs/CertSelfSignedWizard.vue'
import CertCsrWizard from './dialogs/CertCsrWizard.vue'
import CertManager from './dialogs/CertManager.vue'

// ── Kachel-Hub-Navigation ──────────────────────────────────────
const tiles = [
  { key: 'ai', icon: '🤖', title: 'KI-Provider', desc: 'On-Prem (Ollama) oder Cloud-Modell' },
  { key: 'github', icon: '🔗', title: 'GitHub-Integration', desc: 'Token & Repo für Issue-Erstellung' },
  { key: 'modules', icon: '🧩', title: 'Module', desc: 'Reihenfolge & Aktivierung der Module' },
  { key: 'appearance', icon: '🎨', title: 'Erscheinungsbild', desc: 'Darstellung / Theme' },
  { key: 'backup', icon: '💾', title: 'Backup-Einstellungen', desc: 'Backup-on-Exit & Aufbewahrung' },
  { key: 'passkey', icon: '🔑', title: 'Passkey / WebAuthn', desc: 'RP-ID & Origin für Passkeys' },
  { key: 'mfa', icon: '🛡️', title: 'MFA-Richtlinie', desc: 'TOTP/Passkey optional oder Pflicht' },
  { key: 'certs', icon: '📜', title: 'Zertifikate (TLS)', desc: 'Self-Signed, CSR & Verwaltung' },
  { key: 'updates', icon: '⬆️', title: 'Version & Updates', desc: 'Installierte Version prüfen & Update installieren' },
  { key: 'support', icon: '🛟', title: 'Support-Bundle', desc: 'ZIP aller Logs für die Fehlersuche (Secrets redigiert)' },
  { key: 'verordnungen', icon: '📕', title: 'Verordnungstexte', desc: 'Amtliche Fassungen (CRA, KI-VO, DSGVO, NIS-2) in die Installation holen' },
  { key: 'pdf', icon: '🖨️', title: 'PDF-Konverter', desc: 'Zustand des Konverters prüfen (Gotenberg / LibreOffice)' },
] as const

const dialogOnly = ref<string | null>(null)   // SettingsDialog-Sektion (ai/github/modules/appearance/backup)

// ── Verordnungstexte (#1894) ───────────────────────────────────
const verordnungen = ref<any[]>([])
const voBusy = ref('')
const voMsg = ref('')
const voErr = ref('')

// ── PDF-Konverter (#1903) ──────────────────────────────────────
// Bis v8.2.3 fragte die Anwendung den Zustand nie; ein defekter Konverter fiel
// erst am gescheiterten Export eines Anwenders auf — und die Meldung dort nannte
// eine Ursache, die niemand geprüft hatte.
const pdfStatus = ref<any>(null)
const pdfBusy = ref(false)
const pdfErr = ref('')

async function ladePdfKonverter() {
  pdfErr.value = ''
  pdfBusy.value = true
  try {
    const { data } = await axios.get('/api/admin/pdf-konverter')
    pdfStatus.value = data
  } catch (e: any) {
    pdfErr.value = e?.response?.data?.error || 'Zustand nicht abrufbar'
  } finally {
    pdfBusy.value = false
  }
}

async function ladeVerordnungen() {
  voErr.value = ''
  try {
    const { data } = await axios.get('/api/admin/verordnungen')
    verordnungen.value = data?.verordnungen || []
  } catch (e: any) {
    voErr.value = e?.response?.data?.error || 'Stand nicht abrufbar'
  }
}

async function onVerordnungHolen(schluessel: string, vorhanden: boolean) {
  voBusy.value = schluessel
  voMsg.value = ''
  voErr.value = ''
  try {
    // `force` nur, wenn der Text schon vorliegt: Eine amtliche Fassung ändert
    // sich nicht, und ein unnötiger Abruf belastet die Gegenstelle.
    const { data } = await axios.post(
      `/api/admin/verordnungen/${encodeURIComponent(schluessel)}`,
      { force: vorhanden })
    voMsg.value = data?.geholt
      ? `${data.titel} geholt.`
      : (data?.hinweis || 'Unverändert.')
    await ladeVerordnungen()
  } catch (e: any) {
    voErr.value = e?.response?.data?.error || 'Abruf fehlgeschlagen'
  } finally {
    voBusy.value = ''
  }
}
const panel = ref<string | null>(null)         // eigene Panels (passkey/mfa/certs)

const openTile = (key: string) => {
  if (['ai', 'github', 'modules', 'appearance', 'backup'].includes(key)) {
    dialogOnly.value = key
  } else {
    panel.value = key
    if (key === 'certs') loadCurrentCert()
    if (key === 'updates') { admin.fetchVersion(); loadPortainer() }
  }
}

// ── Version & Updates (#1512) + Support-Bundle (#1509) ─────────
const admin = useAdminStore()
const checking = ref(false)
const updating = ref(false)
const bundling = ref(false)
const updMsg = ref('')

const onCheckVersion = async () => {
  checking.value = true
  admin.error = null
  await admin.fetchVersion()
  checking.value = false
}

// ── Release-Kanal + Herkunft (#1908) ───────────────────────────
const herkunft = computed(() => admin.versionInfo?.herkunft || null)
const kanalWahl = ref('')
const kanalSaving = ref(false)
const kanalMsg = ref('')
const kanalOk = ref(false)
const tagKopiert = ref(false)

// Die Auswahl folgt dem Server, solange niemand etwas anderes angeklickt hat.
watch(() => admin.versionInfo?.channel, (c) => {
  if (c && !kanalWahl.value) kanalWahl.value = c
}, { immediate: true })

const onSaveKanal = async () => {
  kanalSaving.value = true
  kanalMsg.value = ''
  try {
    await axios.put('/api/admin/settings', { update: { channel: kanalWahl.value } })
    kanalOk.value = true
    kanalMsg.value = '✓ Kanal gespeichert.'
    // Der Kanal bestimmt, welche Version als „neueste" gilt — also neu fragen.
    await admin.fetchVersion()
  } catch (e: any) {
    kanalOk.value = false
    kanalMsg.value = e?.response?.data?.error || 'Kanal nicht gespeichert.'
  } finally {
    kanalSaving.value = false
    setTimeout(() => (kanalMsg.value = ''), 8000)
  }
}

const onKopiereTag = async () => {
  const wert = `AICS_IMAGE_TAG=${admin.versionInfo?.ziel_tag || ''}`
  tagKopiert.value = await kopiere(wert)
  setTimeout(() => (tagKopiert.value = false), 2500)
}

const onUpdate = async () => {
  const ziel = admin.versionInfo?.latest || ''
  if (!confirm(`Update auf ${ziel || 'die neueste Version im Kanal'} jetzt `
    + 'installieren? Es werden nur die beiden AICS-Images gezogen; '
    + 'Datenbank, Konverter und Ollama bleiben unangetastet. Die Anwendung '
    + 'startet dabei neu.')) return
  updating.value = true
  admin.error = null
  updMsg.value = ''
  let res = await admin.triggerUpdate()
  // #1908: Ein Rückschritt setzt älteren Code auf eine Datenbank mit neuerem
  // Schema. Der Server hält deshalb mit 428 an; die Entscheidung trifft ein
  // Mensch, und zwar mit der Zahl vor Augen.
  if (!res && admin.updateDowngrade) {
    const d = admin.updateDowngrade
    if (confirm(`${d.error}\n\n${d.detail}\n\nTrotzdem fortfahren?`)) {
      res = await admin.triggerUpdate({ confirm_downgrade: true, version: d.ziel })
    }
  }
  updating.value = false
  if (res) {
    updMsg.value = res.message || 'Update angestoßen.'
    setTimeout(() => (updMsg.value = ''), 8000)
  }
}

// ── #1534: Portainer-Zugangsdaten in den Einstellungen ─────────
const pForm = ref<{ base_url: string; stack_id: number | null; endpoint_id: number | null; verify_tls: boolean; api_key: string; api_key_set: boolean }>(
  { base_url: '', stack_id: null, endpoint_id: null, verify_tls: true, api_key: '', api_key_set: false })
const pSaving = ref(false)
const pTesting = ref(false)
const pMsg = ref('')
const pOk = ref(false)

const loadPortainer = async () => {
  try {
    const r = await axios.get('/api/admin/settings')
    const p = (r.data?.integrations?.portainer) || {}
    pForm.value = {
      base_url: p.base_url || '',
      stack_id: p.stack_id ?? null,
      endpoint_id: p.endpoint_id ?? null,
      verify_tls: p.verify_tls !== false,
      api_key: '',                       // nie den (maskierten) Wert vorbelegen
      api_key_set: !!p.api_key_set,
    }
  } catch { /* Panel bleibt mit Defaults */ }
}

const onSavePortainer = async () => {
  pSaving.value = true; pMsg.value = ''; admin.error = null
  try {
    const portainer: any = {
      base_url: pForm.value.base_url.trim(),
      stack_id: pForm.value.stack_id,
      endpoint_id: pForm.value.endpoint_id,
      verify_tls: pForm.value.verify_tls,
    }
    // API-Key nur senden, wenn neu eingegeben (leer = bestehenden behalten)
    if (pForm.value.api_key.trim()) portainer.api_key = pForm.value.api_key.trim()
    await axios.put('/api/admin/settings', { integrations: { portainer } })
    pForm.value.api_key = ''
    pOk.value = true; pMsg.value = '✓ Portainer-Zugangsdaten gespeichert.'
    await loadPortainer()
    await admin.fetchVersion()
    setTimeout(() => (pMsg.value = ''), 6000)
  } catch (e: any) {
    pOk.value = false; pMsg.value = 'Speichern fehlgeschlagen: ' + (e?.response?.data?.error || e?.message || 'Fehler')
  } finally { pSaving.value = false }
}

const onTestPortainer = async () => {
  pTesting.value = true; pMsg.value = ''
  try {
    const r = await axios.post('/api/admin/update/test-connection')
    pOk.value = !!r.data?.ok
    pMsg.value = (pOk.value ? '✓ ' : '⚠ ') + (r.data?.message || r.data?.error || (pOk.value ? 'Verbindung OK.' : 'Fehler.'))
  } catch (e: any) {
    pOk.value = false
    pMsg.value = '⚠ ' + (e?.response?.data?.error || 'Erst speichern, dann testen.')
  } finally { pTesting.value = false }
}

const onSupportBundle = async () => {
  bundling.value = true
  admin.error = null
  updMsg.value = ''
  const fname = await admin.downloadSupportBundle()
  bundling.value = false
  if (fname) { updMsg.value = `Support-Bundle erstellt: ${fname}`; setTimeout(() => (updMsg.value = ''), 6000) }
}

// ── Zertifikate ────────────────────────────────────────────────
const showSelfSigned = ref(false)
const showCsr = ref(false)
const showManager = ref(false)
const certCurrent = ref<any>(null)

const loadCurrentCert = async () => {
  try {
    const r = await axios.get('/api/admin/certificates/current')
    certCurrent.value = r.data
  } catch { certCurrent.value = null }
}
const onCertApplied = () => { loadCurrentCert() }

// ── Passkey / WebAuthn RP-Config (über Web) ────────────────────
interface WaConfig { rp_id: string; rp_name: string; rp_origin: string; from_settings: boolean }
const waConfig = ref<WaConfig>({ rp_id: '', rp_name: '', rp_origin: '', from_settings: false })
const waLoading = ref(true)
const waSaving = ref(false)
const waSavedMsg = ref('')
const waError = ref('')

const rpIdHint = computed(() => {
  const id = (waConfig.value.rp_id || '').trim().toLowerCase().replace(/\.$/, '')
  const origin = (waConfig.value.rp_origin || '').trim()
  if (!id || !origin) return ''
  let host = ''
  try { host = new URL(origin.split(',')[0]).hostname.toLowerCase().replace(/\.$/, '') } catch { return '' }
  if (!host) return ''
  if (host === id || host.endsWith('.' + id)) return ''
  return `RP-ID passt nicht zum Origin-Host „${host}". Nutze „${host}" (oder ein Suffix davon).`
})

const loadWebauthnSuggest = async () => {
  waError.value = ''
  try {
    const r = await axios.get('/api/admin/certificates/suggest')
    const host = (r.data.hostnames || [])[0]
    if (host) {
      waConfig.value.rp_id = host
      if (!waConfig.value.rp_origin) waConfig.value.rp_origin = `https://${host}:8443`
    } else {
      waError.value = 'Kein Hostname erkannt — bitte manuell eintragen.'
    }
  } catch (e: any) {
    waError.value = e?.response?.data?.error || 'Vorschlag konnte nicht geladen werden'
  }
}

const loadWebauthn = async () => {
  waLoading.value = true
  try {
    const r = await axios.get('/api/admin/webauthn-config')
    waConfig.value = {
      rp_id: r.data.rp_id || '',
      rp_name: r.data.rp_name || '',
      rp_origin: r.data.rp_origin || '',
      from_settings: !!r.data.from_settings,
    }
  } catch (e: any) {
    waError.value = e?.response?.data?.error || 'Konfiguration konnte nicht geladen werden'
  } finally {
    waLoading.value = false
  }
}

const saveWebauthn = async () => {
  waSaving.value = true
  waError.value = ''
  waSavedMsg.value = ''
  try {
    await axios.put('/api/admin/webauthn-config', {
      rp_id: waConfig.value.rp_id,
      rp_name: waConfig.value.rp_name,
      rp_origin: waConfig.value.rp_origin,
    })
    waConfig.value.from_settings = true
    waSavedMsg.value = '✓ Gespeichert'
    setTimeout(() => { waSavedMsg.value = '' }, 3000)
  } catch (e: any) {
    waError.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
  } finally {
    waSaving.value = false
  }
}

// ── MFA-Policy (Sprint ε Phase D) ──────────────────────────────
interface MfaPolicy { mode: string; required_roles: string[]; grace_days: number }
const knownRoles = ['admin', 'cra_editor', 'cra_viewer', 'auditor', 'manager']
const mfaPolicy = ref<MfaPolicy>({ mode: 'optional', required_roles: [], grace_days: 7 })
const mfaLoading = ref(true)
const mfaSaving = ref(false)
const mfaSavedMsg = ref('')
const mfaError = ref('')

const toggleRole = (role: string, e: Event) => {
  const checked = (e.target as HTMLInputElement).checked
  const list = mfaPolicy.value.required_roles
  if (checked && !list.includes(role)) list.push(role)
  else if (!checked) mfaPolicy.value.required_roles = list.filter(r => r !== role)
}

const loadMfaPolicy = async () => {
  mfaLoading.value = true
  try {
    const r = await axios.get('/api/admin/mfa-policy')
    mfaPolicy.value = {
      mode: r.data.mode || 'optional',
      required_roles: r.data.required_roles || [],
      grace_days: r.data.grace_days ?? 7,
    }
  } catch (e: any) {
    mfaError.value = e?.response?.data?.error || 'Richtlinie konnte nicht geladen werden'
  } finally {
    mfaLoading.value = false
  }
}

const saveMfaPolicy = async () => {
  mfaSaving.value = true
  mfaError.value = ''
  mfaSavedMsg.value = ''
  try {
    await axios.put('/api/admin/mfa-policy', mfaPolicy.value)
    mfaSavedMsg.value = '✓ Gespeichert'
    setTimeout(() => { mfaSavedMsg.value = '' }, 3000)
  } catch (e: any) {
    mfaError.value = e?.response?.data?.error || 'Speichern fehlgeschlagen'
  } finally {
    mfaSaving.value = false
  }
}

// ── KI-Provider-Status (Sprint #16, #877) ──────────────────────
// #1342 Defekt A: read-only Status aus dem Pinia-Store (Single Source of Truth),
// damit die Karte nach einem Provider-Wechsel ohne Reload aktualisiert.
const aiProviderStore = useAiProviderStore()
const { status: kiStatus, error: kiError } = storeToRefs(aiProviderStore)

onMounted(() => { loadWebauthn(); loadMfaPolicy(); aiProviderStore.loadStatus();
                  ladeVerordnungen(); ladePdfKonverter() })
</script>

<style scoped>
/* #1894 — Verordnungstexte */
.vo-tabelle { width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0; }
.vo-tabelle th, .vo-tabelle td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e0e6ed; vertical-align: top; }
.vo-tabelle .small { font-size: 11px; }
.admin-settings { max-width: 1200px; padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { margin: 0 0 4px; }
.muted { color: var(--color-text-muted, #666); margin: 0 0 12px; }

/* Kachel-Grid */
.tile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}
.settings-tile {
  display: flex; flex-direction: column; gap: 6px; text-align: left;
  background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 10px; padding: 18px 20px; cursor: pointer; font-family: inherit;
  transition: border-color .15s, box-shadow .15s, transform .1s;
}
.settings-tile:hover { border-color: #1565c0; box-shadow: 0 2px 10px rgba(21,101,192,.12); transform: translateY(-1px); }
.tile-icon { font-size: 30px; }
.tile-title { font-size: 16px; font-weight: 600; color: var(--color-primary, #1565c0); }
.tile-desc { font-size: 13px; color: var(--color-text-secondary, #777); line-height: 1.4; }

/* Hub-Modals (Passkey/MFA/Zertifikate) */
.hub-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
  align-items: center; justify-content: center; z-index: 1000; }
.hub-modal { background: #fff; border-radius: 10px; width: min(640px, 94vw); max-height: 90vh;
  display: flex; flex-direction: column; }
.hub-head { display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #e0e0e0; }
.hub-head h2 { margin: 0; font-size: 18px; }
.hub-body { padding: 18px 20px; overflow: auto; }
.x { background: none; border: none; font-size: 18px; cursor: pointer; }

.form-row { margin-bottom: 14px; }
.form-row label { display: block; font-weight: 600; font-size: 13px; margin-bottom: 4px; }
.form-row select, .form-row input {
  width: 100%; padding: 8px 10px; border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 6px; font-size: 14px;
}
.role-checks { display: flex; flex-wrap: wrap; gap: 12px; }
.role-check { display: inline-flex; align-items: center; gap: 6px; font-weight: 400; font-size: 13px; }
.btn-row { display: flex; align-items: center; gap: 12px; margin-top: 8px; flex-wrap: wrap; }
.btn-primary { padding: 10px 16px; background: #1565c0; color: #fff; border: none;
  border-radius: 8px; font-size: 14px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { padding: 10px 16px; background: #f2f2f2; border: 1px solid #d8d8d8;
  border-radius: 8px; font-size: 14px; cursor: pointer; }
.ok { color: #2e7d32; font-size: 13px; }
.err { color: #c62828; font-size: 13px; }
.ok-msg { color: #1b5e20; font-size: 13px; margin-left: 10px; }
.cert-current { font-size: 13px; margin-bottom: 12px; padding: 8px 10px;
  background: var(--color-background, #fafafa); border-radius: 6px; }

/* KI-Provider-Status-Karte (#877) */
.ki-status-card {
  background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e0e0e0);
  border-radius: 10px; padding: 18px 20px; margin-bottom: 20px;
}
.ki-status-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.ki-status-head h2 { margin: 0; font-size: 18px; }
.ki-dl { margin: 8px 0 0; }
.ki-dl-row { display: flex; gap: 12px; padding: 4px 0; border-bottom: 1px solid var(--border-color, #eee); }
.ki-dl-row dt { width: 140px; flex-shrink: 0; font-weight: 600; color: var(--color-text-secondary, #777); }
.ki-dl-row dd { margin: 0; }
.ki-mono { font-family: Consolas, monospace; font-size: 12px; color: var(--color-text-secondary, #999); }
.ki-warn { color: #e65100; font-weight: 600; }
.ki-help { margin-top: 12px; }

/* Version & Updates (#1512) */
.upd-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.upd-label { font-weight: 600; }
.badge { padding: 2px 10px; border-radius: 12px; font-size: 0.85em; font-weight: 600; }
.badge-ok { background: #e6f4ea; color: #1b5e20; }
.badge-warn { background: #fff3e0; color: #b26a00; }
.badge-muted { background: #eceff1; color: #546e7a; }
/* #1534: Portainer-Formular */
.portainer-cfg { margin-top: 18px; padding-top: 14px; border-top: 1px solid #e0e0e0; }
.portainer-cfg h3 { margin: 0 0 10px; font-size: 1rem; color: #1565c0; }
.pf-lbl { display: block; margin-bottom: 10px; font-size: 0.85rem; color: #444; }
.pf-lbl input { display: block; width: 100%; margin-top: 4px; padding: 7px 9px; border: 1px solid #ccc;
  border-radius: 6px; font-size: 0.9rem; box-sizing: border-box; }
.pf-two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.pf-chk { display: flex; align-items: center; gap: 8px; margin: 6px 0 12px; font-size: 0.85rem; color: #444; }
.pf-hint { color: #888; font-weight: 400; font-size: 0.8rem; }
.pf-note { font-size: 0.8rem; margin-top: 10px; line-height: 1.4; }

/* #1908: Release-Kanal + „selbst eintragen" */
.kanal { margin: 12px 0; padding: 10px 12px; border: 1px solid #e0e0e0; border-radius: 8px; }
.kanal h3 { margin: 0 0 8px; font-size: 14px; color: #37474f; }
.kanal-wahl { display: flex; gap: 8px; align-items: flex-start; margin: 6px 0; cursor: pointer; }
.kanal-wahl input { margin-top: 3px; }
.kanal-desc { display: block; margin-top: 1px; }
.selbst { margin: 10px 0; padding: 10px 12px; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafafa; }
.selbst-tag { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 6px 0; }
.selbst-tag code { background: #fff; border: 1px solid #cfd8dc; border-radius: 4px; padding: 3px 7px; }
.selbst-hilfe summary { cursor: pointer; font-size: 12px; color: #1565c0; margin-top: 6px; }
.selbst-hilfe p { margin: 6px 0; }
</style>
