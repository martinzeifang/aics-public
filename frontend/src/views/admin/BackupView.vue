<!--
  Backup-Verwaltung (#1785).

  Bis v8.0.4 sicherte die Funktion nur `data/db/*.sqlite` — Dateien, die seit
  der Umstellung auf PostgreSQL niemand mehr beschreibt. Die Archive sahen aus
  wie Sicherungen und enthielten tote Daten. Format 2 sichert die Datenbank,
  alle Dateien unter `data/` und die Konfiguration.

  Für die Oberfläche folgt daraus eine Vorgabe: Der Unterschied zwischen den
  Formaten ist am Dateinamen nicht zu erkennen, am Inhalt hängt aber alles.
  Deshalb steht er in der Liste, und vor dem Einspielen wird das Archiv gelesen
  und gezeigt — ein Archiv im alten Format stellt die Nutzdaten nicht wieder
  her, und das muss der Anwender sehen, bevor er den Bestand überschreibt.
-->
<template>
  <div class="backup-view">
    <div class="header">
      <h2>Backup-Verwaltung</h2>
      <p>
        Sichert die Datenbank (alle Tabellen und Zeilen), die Dateien unter
        <code>data/</code> — Word-Vorlagen, Gutachten-Exporte, Nachweis-Store —
        und die Konfiguration.
      </p>
    </div>

    <div class="actions">
      <button class="btn-primary" @click="onCreate" :disabled="creating || uploading">
        <span v-if="creating" class="spinner" aria-hidden="true"></span>
        {{ creating ? 'Sicherung läuft…' : '+ Neue Sicherung erstellen' }}
      </button>
      <input ref="fileInput" type="file" accept=".zip" style="display:none"
             @change="onFileChosen" />
      <button class="btn-secondary" @click="fileInput?.click()" :disabled="uploading || creating">
        {{ uploading ? 'Lade hoch…' : '⬆️ Archiv hochladen' }}
      </button>
      <span v-if="creating" class="hint-inline">
        Bei großen Installationen kann das einige Minuten dauern — Seite offen lassen.
      </span>
    </div>

    <FehlerHinweis :text="admin.error" @close="admin.error = null" />
    <FehlerHinweis :text="lastResult" art="erfolg" @close="lastResult = ''" />

    <!-- Ergebnis des Erstellens: die Zahlen belegen, dass etwas drin ist -->
    <div v-if="createResult" class="ergebnis-karte">
      <div class="ergebnis-kopf">
        <strong>Sicherung {{ createResult.id }} erstellt</strong>
        <button type="button" class="karte-schliessen" aria-label="Meldung schließen"
                @click="createResult = null">✕</button>
      </div>
      <p class="zahlen">{{ inhaltText(createResult.inhalt) }}</p>
      <p class="meta">
        Größe {{ formatSize(createResult.size_bytes) }} — die Datei gehört außerhalb
        dieses Servers aufbewahrt.
      </p>
      <ul v-if="createResult.hinweise?.length" class="warn-liste">
        <li v-for="(h, i) in createResult.hinweise" :key="i">{{ h }}</li>
      </ul>
    </div>

    <!-- Ergebnis des Einspielens -->
    <div v-if="restoreResult" class="ergebnis-karte" :class="{ warn: restoreWarnungen.length }">
      <div class="ergebnis-kopf">
        <strong v-if="restoreResult.uebernommen">Mandanten übernommen</strong>
        <strong v-else>Wiederherstellung abgeschlossen</strong>
        <button type="button" class="karte-schliessen" aria-label="Meldung schließen"
                @click="restoreResult = null">✕</button>
      </div>
      <p class="zahlen" v-if="restoreResult.uebernommen">
        {{ (restoreResult.mandanten || []).join(', ') || '—' }} —
        {{ nf(restoreResult.tabellen) }} Tabellen ·
        {{ nf(restoreResult.zeilen) }} Zeilen eingefügt
      </p>
      <p class="zahlen" v-else>
        {{ formatArchivformat(restoreResult.format) }} —
        {{ nf(restoreResult.tabellen) }} Tabellen ·
        {{ nf(restoreResult.zeilen) }} Zeilen ·
        {{ nf(restoreResult.dateien) }} Dateien ·
        {{ nf(restoreResult.konfiguration) }} Konfigurationsdateien
      </p>
      <!-- Beim Restore trägt `uebersprungen` Tabellennamen (#1813), beim
           Übernehmen Mandantennamen — die Beschriftung passt nur hier. -->
      <p v-if="restoreResult.uebernommen && restoreResult.uebersprungen?.length" class="meta">
        Übersprungen (gibt es hier schon):
        {{ restoreResult.uebersprungen.join(', ') }}
      </p>
      <p v-if="restoreResult.safety_backup" class="meta">
        Sicherheitskopie des vorherigen Stands:
        <code>{{ restoreResult.safety_backup }}</code>
      </p>
      <p v-if="restoreResult.hinweis" class="hinweis-zeile">{{ restoreResult.hinweis }}</p>
      <div v-if="restoreWarnungen.length" class="warn-block">
        <div class="warn-kopf">
          {{ nf(restoreWarnungen.length) }}
          {{ restoreWarnungen.length === 1 ? 'Warnung' : 'Warnungen' }}
        </div>
        <ul class="warn-liste scrollbar">
          <li v-for="(w, i) in restoreWarnungen" :key="i">{{ w }}</li>
        </ul>
      </div>
    </div>

    <div class="backup-table">
      <table>
        <thead>
          <tr>
            <th>Archiv</th>
            <th>Erstellt am</th>
            <th>Größe</th>
            <th>Inhalt</th>
            <th>Aktionen</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in admin.backups" :key="b.id">
            <td>
              <code>{{ b.id }}</code>
              <span v-if="b.art === 'pre_restore'" class="chip chip-neutral"
                    title="Automatisch vor einer Wiederherstellung angelegt">
                Sicherheitskopie
              </span>
            </td>
            <td>{{ formatDate(b.created_at) }}</td>
            <td>{{ formatSize(b.size_bytes) }}</td>
            <td>
              <template v-if="b.format === 2 && b.inhalt">
                <span class="zahlen-zelle">{{ inhaltText(b.inhalt) }}</span>
                <span v-if="b.app_version" class="meta-klein">Version {{ b.app_version }}</span>
              </template>
              <span v-else-if="b.format === 1" class="chip chip-warn"
                    title="Archiv aus der SQLite-Zeit: enthält den Inhalt der PostgreSQL-Datenbank nicht">
                altes Format — ohne Datenbank
              </span>
              <span v-else class="chip chip-danger">nicht lesbar</span>
            </td>
            <td class="action-cell">
              <button class="btn-secondary" @click="onDownload(b.id)"
                      :disabled="downloading === b.id">
                {{ downloading === b.id ? 'Lade…' : '⬇️ Herunterladen' }}
              </button>
              <button class="btn-secondary" @click="onUebernehmen(b.id)"
                      :disabled="restoring !== null || b.format !== 2"
                      title="Mandanten aus diesem Archiv einfügen, ohne den eigenen Bestand zu löschen">
                📥 Übernehmen
              </button>
              <button class="btn-warn" @click="onRestore(b.id)"
                      :disabled="restoring !== null">
                {{ restoring === b.id ? 'Stelle wieder her…' : 'Wiederherstellen' }}
              </button>
              <button class="btn-danger" @click="onDelete(b.id)"
                      :disabled="restoring !== null">Löschen</button>
            </td>
          </tr>
          <tr v-if="!admin.loading && admin.backups.length === 0">
            <td colspan="5" class="empty">Keine Sicherungen vorhanden.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Wiederherstellen: erst zeigen, was drinsteckt, dann fragen -->
    <div v-if="confirmRestore" class="modal-overlay" @mousedown.self="closeConfirm">
      <div class="modal-content" role="dialog" aria-modal="true">
        <h3>Sicherung wiederherstellen?</h3>
        <p class="modal-intro">
          Archiv <code>{{ confirmRestore }}</code> wird eingespielt. Vor dem Einspielen
          legt der Server eine Sicherheitskopie des aktuellen Stands an.
        </p>

        <p v-if="inhaltLaden" class="laden">Archiv wird gelesen…</p>

        <template v-else-if="inhalt">
          <div class="inhalt-box">
            <div class="inhalt-zeile">
              <span class="label">Format</span>
              <span>{{ formatArchivformat(inhalt.format) }}</span>
            </div>
            <div class="inhalt-zeile">
              <span class="label">Erstellt am</span>
              <span>{{ formatDate(inhalt.created_at) }}</span>
            </div>
            <div class="inhalt-zeile" v-if="inhalt.app_version">
              <span class="label">Suite-Version</span>
              <span>{{ inhalt.app_version }}</span>
            </div>
            <div class="inhalt-zeile">
              <span class="label">Datenbank</span>
              <span>
                {{ nf(inhalt.tabellen) }} Tabellen ·
                {{ inhalt.zeilen == null ? 'Zeilenzahl nicht vermerkt' : nf(inhalt.zeilen) + ' Zeilen' }}
              </span>
            </div>
            <div class="inhalt-zeile">
              <span class="label">Dateien</span>
              <span>{{ nf(inhalt.dateien) }}</span>
            </div>
          </div>

          <div v-if="inhaltWarnungen.length" class="warn-block prominent">
            <div class="warn-kopf">Vor dem Einspielen beachten</div>
            <ul class="warn-liste scrollbar">
              <li v-for="(w, i) in inhaltWarnungen" :key="i">{{ w }}</li>
            </ul>
          </div>
        </template>

        <p v-else class="laden">
          Der Inhalt des Archivs konnte nicht gelesen werden. Ein Einspielen ist
          damit nicht abschätzbar.
        </p>

        <!-- #1813: Was ersetzt wird, entscheidet der Betreiber. Vorausgewählt
             ist „nur Fachdaten": Ein Archiv stammt oft von einer anderen
             Installation, und die Konten gehören zur Installation, nicht zu
             den Daten. Wer das übersieht, sperrt sich aus. -->
        <fieldset class="umfang">
          <legend>Was soll eingespielt werden?</legend>
          <label class="umfang-option">
            <input type="radio" value="fachdaten" v-model="umfang" />
            <span>
              <strong>Nur Fachdaten</strong> — Firmen, Projekte, Bewertungen, Nachweise.
              <em>Benutzerkonten, Rollen, Passkeys und der Revisionspfad dieser
              Installation bleiben unverändert.</em>
            </span>
          </label>
          <label class="umfang-option">
            <input type="radio" value="alles" v-model="umfang" />
            <span>
              <strong>Fachdaten und Benutzer</strong> — vollständiger Stand des Archivs.
              <em>Für den Wiederanlauf derselben Installation. Die Konten dieser
              Installation werden ersetzt.</em>
            </span>
          </label>
          <label class="umfang-option">
            <input type="radio" value="nur_benutzer" v-model="umfang" />
            <span>
              <strong>Nur Benutzer</strong> — ausschließlich Konten und Rollen.
              <em>Etwa, um Zugänge aus einer Sicherung zurückzuholen.</em>
            </span>
          </label>
        </fieldset>

        <!-- #1809: „Sind Sie sicher?" ohne Zahlen ist keine Warnung. -->
        <div v-if="vorschauLaden" class="laden">Abgleich mit dem aktuellen Stand …</div>
        <div v-else-if="vorschau" class="vorschau">
          <div class="vorschau-kopf">
            Was sich ändert
            <span v-if="vorschau.verlust_gesamt > 0" class="verlust-marke">
              {{ nf(vorschau.verlust_gesamt) }} Datensätze werden entfernt
            </span>
            <span v-else class="kein-verlust">kein Datenverlust erkennbar</span>
          </div>
          <table class="vorschau-tabelle">
            <thead>
              <tr><th>Bereich</th><th>im Archiv</th><th>aktuell</th><th>Folge</th></tr>
            </thead>
            <tbody>
              <tr v-for="z in vorschauZeilen" :key="z.schema + z.tabelle"
                  :class="{ verlust: z.verlust > 0, unberuehrt: !z.betroffen }">
                <td>{{ z.bezeichnung }}</td>
                <td>{{ z.im_archiv == null ? '—' : nf(z.im_archiv) }}</td>
                <td>{{ z.im_ziel == null ? '—' : nf(z.im_ziel) }}</td>
                <td>
                  <template v-if="!z.betroffen">bleibt unverändert</template>
                  <template v-else-if="z.verlust > 0">
                    −{{ nf(z.verlust) }} werden entfernt
                  </template>
                  <template v-else>wird ersetzt</template>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="vorschau.installation_unberuehrt" class="hinweis-zeile">
            Konten, Rollen, Passkeys und der Revisionspfad dieser Installation
            bleiben unangetastet.
          </p>
        </div>

        <p class="warnsatz" v-if="umfang === 'alles'">
          Der aktuelle Datenbestand wird überschrieben — einschließlich der
          Benutzerkonten dieser Installation.
        </p>
        <p class="warnsatz" v-else>Die betroffenen Bestände werden überschrieben.</p>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeConfirm">Abbrechen</button>
          <button class="btn-danger" @click="executeRestore" :disabled="inhaltLaden">
            Bestätigen und wiederherstellen
          </button>
        </div>
      </div>
    </div>

    <!--
      Übernehmen (#1808/#1810): Mandanten eines fremden Archivs einfügen.
      Bewusst ein eigener Dialog und nicht eine Option des Restores — es ist
      der gegenteilige Vorgang. Hier geht nichts verloren, deshalb gibt es
      keine Sicherheitskopie und keine rote Warnung, sondern eine Auswahl.
    -->
    <div v-if="confirmUebernahme" class="modal-overlay" @mousedown.self="closeUebernahme">
      <div class="modal-content breit" role="dialog" aria-modal="true">
        <h3>Daten aus einem anderen Stand übernehmen</h3>
        <p class="modal-intro">
          Aus <code>{{ confirmUebernahme }}</code> werden die ausgewählten Mandanten
          <strong>eingefügt</strong>. Der vorhandene Bestand dieser Installation
          bleibt unverändert — es wird nichts geleert und nichts überschrieben.
        </p>

        <div v-if="mandantenLaden" class="laden">Archiv wird gelesen …</div>
        <template v-else-if="archivMandanten.length">
          <div class="auswahl-kopf">
            <label class="umfang-option">
              <input type="checkbox" :checked="alleGewaehlt"
                     @change="alleUmschalten(($event.target as HTMLInputElement).checked)" />
              <span>Alle {{ archivMandanten.length }} Mandanten</span>
            </label>
            <span class="meta-klein">{{ gewaehlt.length }} ausgewählt</span>
          </div>

          <table class="vorschau-tabelle">
            <thead>
              <tr><th></th><th>Mandant</th><th>Projekte im Archiv</th><th>Hier schon vorhanden</th></tr>
            </thead>
            <tbody>
              <tr v-for="m in archivMandanten" :key="m.name">
                <td>
                  <input type="checkbox" :value="m.name" v-model="gewaehlt" />
                </td>
                <td>
                  <strong>{{ m.name }}</strong>
                  <span v-if="m.unternehmen && m.unternehmen !== m.name" class="meta-klein">
                    {{ m.unternehmen }}
                  </span>
                </td>
                <td>
                  <span v-if="!m.projekte.length" class="meta-klein">—</span>
                  <span v-for="p in m.projekte" :key="p.schema + p.name" class="chip chip-neutral"
                        :title="p.name">
                    {{ p.modul }}<template v-if="p.im_ziel"> ✓</template>
                  </span>
                </td>
                <td>
                  <span v-if="m.im_ziel" class="chip chip-warn">ja</span>
                  <span v-else-if="m.im_ziel_gelöscht" class="chip chip-neutral"
                        title="Der Mandant ist hier als gelöscht markiert. Beim Übernehmen wird er wieder eingesetzt.">
                    gelöscht
                  </span>
                  <span v-else class="chip chip-neutral">nein</span>
                </td>
              </tr>
            </tbody>
          </table>

          <fieldset class="umfang" v-if="kollisionen.length">
            <legend>{{ kollisionen.length }} ausgewählte Mandanten gibt es hier schon</legend>
            <label class="umfang-option">
              <input type="radio" value="behalten" v-model="beiKollision" />
              <span>
                <strong>Bestand behalten</strong> — diese Mandanten werden übersprungen.
                Der hiesige Stand ist eine Aussage; sie bleibt stehen.
              </span>
            </label>
            <label class="umfang-option">
              <input type="radio" value="ersetzen" v-model="beiKollision" />
              <span>
                <strong>Durch den Stand aus dem Archiv ersetzen</strong> — die Daten
                dieser Mandanten werden hier entfernt und neu eingefügt.
                Andere Mandanten sind nicht betroffen.
              </span>
            </label>
          </fieldset>

          <label class="umfang-option">
            <input type="checkbox" v-model="mitBenutzern" />
            <span>
              Benutzerkonten, Gruppen und Mitgliedschaften mit übernehmen.
              Passkeys bleiben zurück — sie gelten nur für die Domain, unter der
              sie angelegt wurden, und würden hier ein Konto erzeugen, das
              niemand öffnen kann.
            </span>
          </label>

          <p class="hinweis-zeile">
            Hochgeladene Dateien der übernommenen Datensätze — Word-Vorlagen,
            Nachweisdokumente, finalisierte Gutachten, Pentest-Berichte — werden
            mit ergänzt. Dateien, die hier schon liegen, bleiben unberührt.
          </p>

          <div v-if="probe" class="vorschau">
            <div class="vorschau-kopf">
              <strong>Probelauf</strong>
              <span class="verlust-marke neutral">
                {{ nf(probe.zeilen) }} Zeilen in {{ nf(probe.tabellen) }} Tabellen
              </span>
            </div>
            <p v-if="probe.uebersprungen?.length" class="hinweis-zeile">
              Übersprungen: {{ probe.uebersprungen.join(', ') }}
            </p>
            <ul v-if="probeWarnungen.length" class="warn-liste">
              <li v-for="(w, i) in probeWarnungen" :key="i">{{ w }}</li>
            </ul>
          </div>
        </template>
        <p v-else class="warnsatz">
          Das Archiv enthält keine übernehmbaren Mandanten.
        </p>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeUebernahme">Abbrechen</button>
          <button class="btn-secondary" @click="executeUebernahme(true)"
                  :disabled="!gewaehlt.length || uebernehmend">
            Probelauf
          </button>
          <button class="btn-warn" @click="executeUebernahme(false)"
                  :disabled="!gewaehlt.length || uebernehmend">
            {{ uebernehmend ? 'Übernehme…' : 'Übernehmen' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAdminStore } from '../../stores/admin'
import FehlerHinweis from '../../components/shared/FehlerHinweis.vue'

type Inhalt = {
  tabellen?: number | null
  zeilen?: number | null
  dateien?: number | null
  konfiguration?: number | null
}

const admin = useAdminStore()
const creating = ref(false)
const uploading = ref(false)
const restoring = ref<string | null>(null)
const downloading = ref<string | null>(null)
const confirmRestore = ref<string | null>(null)
const lastResult = ref('')
const createResult = ref<any>(null)
const restoreResult = ref<any>(null)
const inhalt = ref<any>(null)
const inhaltLaden = ref(false)
// #1813/#1809: gewählter Umfang und der daraus berechnete Abgleich.
const umfang = ref<'fachdaten' | 'alles' | 'nur_benutzer'>('fachdaten')
const vorschau = ref<any>(null)
const vorschauLaden = ref(false)
const vorschauZeilen = computed<any[]>(() =>
  (vorschau.value?.positionen || []).filter((z: any) => z.im_archiv != null || z.im_ziel))
const fileInput = ref<HTMLInputElement | null>(null)

const inhaltWarnungen = computed<string[]>(() => inhalt.value?.warnungen || [])
const restoreWarnungen = computed<string[]>(() => restoreResult.value?.warnungen || [])

/** Zahlen mit deutschem Tausendertrennzeichen; fehlende Angabe als „–". */
const nf = (n: number | null | undefined): string =>
  typeof n === 'number' && isFinite(n) ? n.toLocaleString('de-DE') : '–'

const inhaltText = (i: Inhalt | null | undefined): string => {
  if (!i) return 'Inhalt nicht vermerkt'
  const teile = [
    `${nf(i.tabellen)} Tabellen`,
    `${nf(i.zeilen)} Zeilen`,
    `${nf(i.dateien)} Dateien`,
  ]
  if (typeof i.konfiguration === 'number') {
    teile.push(`${nf(i.konfiguration)} Konfigurationsdateien`)
  }
  return teile.join(' · ')
}

const formatArchivformat = (f: number | null | undefined): string => {
  if (f === 2) return 'Format 2 — vollständige Sicherung'
  if (f === 1) return 'Format 1 — altes Format, ohne Datenbankinhalt'
  return 'Format unbekannt'
}

const formatDate = (iso: string | null | undefined): string => {
  if (!iso) return '–'
  try {
    return new Date(iso).toLocaleString('de-DE')
  } catch {
    return iso
  }
}

const formatSize = (b: number | null | undefined): string => {
  if (typeof b !== 'number') return '–'
  if (b < 1024) return `${b} B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`
  return `${(b / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

const onFileChosen = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.zip')) {
    admin.error = 'Nur .zip-Dateien werden angenommen.'
    input.value = ''
    return
  }
  uploading.value = true
  lastResult.value = ''
  admin.error = null
  const result = await admin.uploadBackup(file)
  uploading.value = false
  input.value = ''
  if (result) {
    lastResult.value = `Archiv hochgeladen: ${result.id} (${formatSize(result.size_bytes)}). `
      + 'Das Format steht in der Spalte „Inhalt".'
  }
}

const onCreate = async () => {
  creating.value = true
  lastResult.value = ''
  createResult.value = null
  admin.error = null
  const result = await admin.createBackup()
  creating.value = false
  if (result) createResult.value = result
}

const onDownload = async (id: string) => {
  downloading.value = id
  admin.error = null
  const fname = await admin.downloadBackup(id)
  downloading.value = null
  if (fname) {
    lastResult.value = `${fname} heruntergeladen — die Datei gehört außerhalb dieses Servers aufbewahrt.`
  }
}

const onDelete = async (id: string) => {
  if (!confirm(`Archiv ${id} wirklich löschen?`)) return
  admin.error = null
  await admin.deleteBackup(id)
}

const onRestore = async (id: string) => {
  confirmRestore.value = id
  inhalt.value = null
  inhaltLaden.value = true
  admin.error = null
  const beschreibung = await admin.backupInhalt(id)
  // Zwischenzeitliches Abbrechen soll keine fremde Beschreibung nachziehen.
  if (confirmRestore.value !== id) return
  inhalt.value = beschreibung
  inhaltLaden.value = false
  await ladeVorschau(id)
}

/** Abgleich Archiv ↔ aktueller Stand für den gewählten Umfang. */
const ladeVorschau = async (id: string) => {
  vorschauLaden.value = true
  vorschau.value = null
  const v = await admin.backupVorschau(id, umfang.value)
  if (confirmRestore.value !== id) return
  vorschau.value = v
  vorschauLaden.value = false
}

// Wechselt der Umfang, ändert sich auch, was verloren ginge.
watch(umfang, () => { if (confirmRestore.value) ladeVorschau(confirmRestore.value) })

const closeConfirm = () => {
  confirmRestore.value = null
  inhalt.value = null
  inhaltLaden.value = false
  vorschau.value = null
  vorschauLaden.value = false
}

const executeRestore = async () => {
  if (!confirmRestore.value) return
  const id = confirmRestore.value
  const gewaehlterUmfang = umfang.value
  closeConfirm()
  restoring.value = id
  lastResult.value = ''
  restoreResult.value = null
  admin.error = null
  const bericht = await admin.restoreBackup(id, gewaehlterUmfang)
  restoring.value = null
  if (bericht) {
    restoreResult.value = bericht
    await admin.fetchBackups()
  }
}

// ── Übernehmen (#1808/#1810) ───────────────────────────────────────────────
// Der Gegenentwurf zum Restore: Es wird nur eingefügt. Deshalb keine
// Sicherheitskopie und keine rote Warnung, sondern eine Auswahl — und ein
// Probelauf, der dieselben Zahlen liefert, ohne zu schreiben.

const confirmUebernahme = ref<string | null>(null)
const mandantenLaden = ref(false)
const archivMandanten = ref<any[]>([])
const gewaehlt = ref<string[]>([])
const beiKollision = ref<'behalten' | 'ersetzen'>('behalten')
const mitBenutzern = ref(false)
const uebernehmend = ref(false)
const probe = ref<any>(null)

const alleGewaehlt = computed(() =>
  archivMandanten.value.length > 0 && gewaehlt.value.length === archivMandanten.value.length)

/** Nur die *ausgewählten* Mandanten zählen — die Frage stellt sich sonst nicht. */
const kollisionen = computed(() =>
  archivMandanten.value.filter((m) => m.im_ziel && gewaehlt.value.includes(m.name)))

const probeWarnungen = computed<string[]>(() => probe.value?.warnungen ?? [])

const alleUmschalten = (an: boolean) => {
  gewaehlt.value = an ? archivMandanten.value.map((m) => m.name) : []
}

const onUebernehmen = async (id: string) => {
  confirmUebernahme.value = id
  archivMandanten.value = []
  gewaehlt.value = []
  probe.value = null
  beiKollision.value = 'behalten'
  mitBenutzern.value = false
  mandantenLaden.value = true
  admin.error = null
  const daten = await admin.backupMandanten(id)
  if (confirmUebernahme.value !== id) return
  archivMandanten.value = daten?.mandanten ?? []
  // Vorauswahl: alles, was es hier noch nicht gibt. Das ist der Normalfall,
  // und was schon da ist, soll man ausdrücklich anklicken.
  gewaehlt.value = archivMandanten.value.filter((m) => !m.im_ziel).map((m) => m.name)
  mandantenLaden.value = false
}

const closeUebernahme = () => {
  confirmUebernahme.value = null
  archivMandanten.value = []
  gewaehlt.value = []
  probe.value = null
  mandantenLaden.value = false
}

const executeUebernahme = async (trockenlauf: boolean) => {
  if (!confirmUebernahme.value) return
  const id = confirmUebernahme.value
  // „Ersetzen" ist der einzige Weg, auf dem hier etwas gelöscht wird. Die
  // Radiogruppe ist eine Einstellung; der Griff nach dem Knopf soll noch
  // einmal benennen, was passiert — und für welche Mandanten.
  if (!trockenlauf && beiKollision.value === 'ersetzen' && kollisionen.value.length) {
    const namen = kollisionen.value.map((m) => m.name).join(', ')
    if (!confirm(
      `Daten dieser Mandanten hier entfernen und durch den Stand aus dem `
      + `Archiv ersetzen?\n\n${namen}\n\n`
      + 'Andere Mandanten sind nicht betroffen. Vorher legt der Server eine '
      + 'Sicherheitskopie des aktuellen Stands an.')) return
  }
  uebernehmend.value = true
  admin.error = null
  const bericht = await admin.backupUebernehmen(id, [...gewaehlt.value], {
    beiKollision: beiKollision.value,
    mitBenutzern: mitBenutzern.value,
    trockenlauf,
  })
  uebernehmend.value = false
  if (!bericht) return
  if (trockenlauf) {
    probe.value = bericht
    return
  }
  closeUebernahme()
  restoreResult.value = {
    ...bericht,
    hinweis: 'Die übernommenen Mandanten stehen jetzt neben dem bisherigen '
           + 'Bestand. Nichts wurde gelöscht.',
  }
  await admin.fetchBackups()
}

onMounted(() => admin.fetchBackups())
</script>

<style scoped>
.backup-view {
  max-width: 1180px;
}

.header {
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}

.header h2 {
  margin: 0;
  font-size: 22px;
}

.header p {
  margin: 2px 0 0;
  color: #888;
  font-size: 13px;
  max-width: 820px;
}

.header code {
  font-size: 12px;
}

.actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.hint-inline {
  color: #6d4c41;
  font-size: 12px;
}

.spinner {
  display: inline-block;
  width: 11px;
  height: 11px;
  margin-right: 6px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: dreh 0.8s linear infinite;
  vertical-align: -1px;
}

@keyframes dreh {
  to { transform: rotate(360deg); }
}

/* ── Ergebnis-Karten ──────────────────────────────────────────── */
.ergebnis-karte {
  background: #e8f5e9;
  border: 1px solid #a5d6a7;
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 14px;
  font-size: 13px;
  color: #1b5e20;
}

.ergebnis-karte.warn {
  background: #fff8e1;
  border-color: #ffe082;
  color: #5d4037;
}

.ergebnis-kopf {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.karte-schliessen {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 4px;
}

.karte-schliessen:hover { opacity: 1; background: rgba(0, 0, 0, 0.07); }

.ergebnis-karte .zahlen {
  margin: 6px 0 0;
  font-variant-numeric: tabular-nums;
}

.ergebnis-karte .meta,
.ergebnis-karte .hinweis-zeile {
  margin: 4px 0 0;
  opacity: 0.85;
}

.warn-block {
  margin-top: 10px;
  padding: 10px 12px;
  background: #fff8e1;
  border: 1px solid #ffe082;
  border-radius: 6px;
  color: #5d4037;
}

.warn-block.prominent {
  background: #ffebee;
  border-color: #ef9a9a;
  color: #b71c1c;
}

.warn-kopf {
  font-weight: 600;
  margin-bottom: 6px;
}

.warn-liste {
  margin: 0;
  padding-left: 20px;
}

.warn-liste li {
  margin: 3px 0;
  overflow-wrap: anywhere;
}

/* Warnungen können zahlreich sein — scrollen statt abschneiden. */
.scrollbar {
  max-height: 220px;
  overflow-y: auto;
}

/* ── Tabelle ──────────────────────────────────────────────────── */
.backup-table {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  overflow: hidden;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th {
  background: #f5f5f5;
  text-align: left;
  padding: 10px;
  font-weight: 600;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}

td {
  padding: 10px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
}

.zahlen-zelle {
  display: block;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.meta-klein {
  display: block;
  color: #888;
  font-size: 11px;
  margin-top: 2px;
}

.chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid;
  white-space: nowrap;
}

.chip-neutral {
  margin-left: 6px;
  background: #eceff1;
  border-color: #b0bec5;
  color: #455a64;
}

.chip-warn {
  background: #fff3e0;
  border-color: #ffb74d;
  color: #e65100;
}

.chip-danger {
  background: #ffebee;
  border-color: #ef9a9a;
  color: #c62828;
}

.action-cell {
  display: flex;
  gap: 8px;
  white-space: nowrap;
}

.empty {
  padding: 40px !important;
  text-align: center;
  color: #888;
}

.btn-primary,
.btn-warn,
.btn-danger,
.btn-secondary {
  padding: 6px 14px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-primary:disabled,
.btn-warn:disabled,
.btn-danger:disabled,
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: default;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-warn {
  background: #ff9800;
  color: white;
}

.btn-warn:hover:not(:disabled) {
  background: #f57c00;
}

.btn-danger {
  background: #d32f2f;
  color: white;
}

.btn-danger:hover:not(:disabled) {
  background: #b71c1c;
}

.btn-secondary {
  background: #e0e0e0;
  color: #333;
}

/* ── Bestätigungsdialog ───────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

.modal-content {
  background: white;
  border-radius: 8px;
  padding: 24px;
  max-width: 560px;
  width: 100%;
  max-height: 100%;
  overflow-y: auto;
  font-size: 13px;
}

.modal-content h3 {
  margin: 0 0 12px;
  color: #d32f2f;
  font-size: 17px;
}

.modal-intro {
  margin: 0 0 12px;
}

.laden {
  margin: 0 0 12px;
  color: #666;
}

.inhalt-box {
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 10px 12px;
  background: #fafafa;
}

.inhalt-zeile {
  display: flex;
  gap: 12px;
  padding: 3px 0;
}

.inhalt-zeile .label {
  flex: 0 0 130px;
  color: #666;
}

.warnsatz {
  margin: 14px 0 0;
  font-weight: 600;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

/* #1813/#1809: Umfang-Wahl und Verlust-Vorschau im Bestätigungsdialog. */
.umfang { border: 1px solid #cfd8e3; border-radius: 8px; padding: 10px 12px; margin: 12px 0; }
.umfang legend { font-size: 13px; font-weight: 600; color: #37474f; padding: 0 6px; }
.umfang-option { display: flex; gap: 8px; align-items: flex-start; margin: 6px 0; font-size: 13px; }
.umfang-option em { display: block; color: #607d8b; font-style: normal; font-size: 12px; }
.vorschau { margin: 12px 0; }
.vorschau-kopf { display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; font-weight: 600; color: #37474f; margin-bottom: 6px; }
.verlust-marke { color: #c62828; font-weight: 600; }
/* Übernahme-Dialog (#1808): breiter, weil die Projektspalte Platz braucht. */
.modal-content.breit { max-width: 860px; }
.auswahl-kopf {
  display: flex; justify-content: space-between; align-items: center;
  margin: 12px 0 6px; padding-bottom: 6px; border-bottom: 1px solid #eceff1;
}
.verlust-marke.neutral { color: #37474f; }
.vorschau-tabelle .chip { margin-right: 4px; }

.kein-verlust { color: #2e7d32; font-weight: 500; }
.vorschau-tabelle { width: 100%; border-collapse: collapse; font-size: 12px; }
.vorschau-tabelle th, .vorschau-tabelle td { text-align: left; padding: 3px 6px; border-bottom: 1px solid #eceff1; }
.vorschau-tabelle th { color: #607d8b; font-weight: 600; }
.vorschau-tabelle tr.verlust td { background: #fff3e0; }
.vorschau-tabelle tr.unberuehrt td { color: #90a4ae; }
</style>
