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
      <h2>{{ $t('admin.backupView.backupVerwaltung') }}</h2>
      <p>
        {{ $t('admin.backupView.sichertDieDatenbankAlleTabellenUndZe') }}
        <code>data/</code> {{ $t('admin.backupView.wordVorlagenGutachtenExporteNachweis') }}
      </p>
    </div>

    <div class="actions">
      <button class="btn-primary" @click="onCreate" :disabled="creating || uploading">
        <span v-if="creating" class="spinner" aria-hidden="true"></span>
        {{ creating ? $t('admin.backupView.sicherungLauft') : $t('admin.backupView.neueSicherungErstellen') }}
      </button>
      <input ref="fileInput" type="file" accept=".zip" style="display:none"
             @change="onFileChosen" />
      <button class="btn-secondary" @click="fileInput?.click()" :disabled="uploading || creating">
        {{ uploading ? $t('admin.backupView.ladeHoch') : $t('admin.backupView.archivHochladen') }}
      </button>
      <span v-if="creating" class="hint-inline">
        {{ $t('admin.backupView.beiGrossenInstallationenKannDasEinig') }}
      </span>
    </div>

    <FehlerHinweis :text="admin.error" @close="admin.error = null" />
    <FehlerHinweis :text="lastResult" art="erfolg" @close="lastResult = ''" />

    <!-- Ergebnis des Erstellens: die Zahlen belegen, dass etwas drin ist -->
    <div v-if="createResult" class="ergebnis-karte">
      <div class="ergebnis-kopf">
        <strong>{{ $t('admin.backupView.sicherungV0Erstellt', { v0: createResult.id }) }}</strong>
        <button type="button" class="karte-schliessen" :aria-label="$t('admin.backupView.meldungSchliessen')"
                @click="createResult = null">✕</button>
      </div>
      <p class="zahlen">{{ inhaltText(createResult.inhalt) }}</p>
      <p class="meta">
        {{ $t('admin.backupView.grosseV0DieDateiGehortAusserhalbDies', { v0: formatSize(createResult.size_bytes) }) }}
      </p>
      <ul v-if="createResult.hinweise?.length" class="warn-liste">
        <li v-for="(h, i) in createResult.hinweise" :key="i">{{ h }}</li>
      </ul>
    </div>

    <!-- Ergebnis des Einspielens -->
    <div v-if="restoreResult" class="ergebnis-karte" :class="{ warn: restoreWarnungen.length }">
      <div class="ergebnis-kopf">
        <strong v-if="restoreResult.uebernommen">{{ $t('admin.backupView.mandantenUbernommen') }}</strong>
        <strong v-else>{{ $t('admin.backupView.wiederherstellungAbgeschlossen') }}</strong>
        <button type="button" class="karte-schliessen" :aria-label="$t('admin.backupView.meldungSchliessen')"
                @click="restoreResult = null">✕</button>
      </div>
      <p class="zahlen" v-if="restoreResult.uebernommen">
        {{ $t('admin.backupView.v0V1TabellenV2ZeilenEingefugt', { v0: (restoreResult.mandanten || []).join(', ') || '—', v1: nf(restoreResult.tabellen), v2: nf(restoreResult.zeilen) }) }}
      </p>
      <p class="zahlen" v-else>
        {{ $t('admin.backupView.v0V1TabellenV2ZeilenV3DateienV4Konfi', { v0: formatArchivformat(restoreResult.format), v1: nf(restoreResult.tabellen), v2: nf(restoreResult.zeilen), v3: nf(restoreResult.dateien), v4: nf(restoreResult.konfiguration) }) }}
      </p>
      <!-- Beim Restore trägt `uebersprungen` Tabellennamen (#1813), beim
           Übernehmen Mandantennamen — die Beschriftung passt nur hier. -->
      <p v-if="restoreResult.uebernommen && restoreResult.uebersprungen?.length" class="meta">
        {{ $t('admin.backupView.ubersprungenGibtEsHierSchonV0', { v0: restoreResult.uebersprungen.join(', ') }) }}
      </p>
      <p v-if="restoreResult.safety_backup" class="meta">
        {{ $t('admin.backupView.sicherheitskopieDesVorherigenStands') }}
        <code>{{ restoreResult.safety_backup }}</code>
      </p>
      <p v-if="restoreResult.hinweis" class="hinweis-zeile">{{ restoreResult.hinweis }}</p>
      <div v-if="restoreWarnungen.length" class="warn-block">
        <div class="warn-kopf">
          {{ nf(restoreWarnungen.length) }}
          {{ restoreWarnungen.length === 1 ? $t('admin.backupView.warnung') : $t('admin.backupView.warnungen') }}
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
            <th>{{ $t('admin.backupView.archiv') }}</th>
            <th>{{ $t('common.erstelltAm') }}</th>
            <th>{{ $t('admin.backupView.grosse') }}</th>
            <th>{{ $t('admin.backupView.inhalt') }}</th>
            <th>{{ $t('common.actions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in admin.backups" :key="b.id">
            <td>
              <code>{{ b.id }}</code>
              <span v-if="b.art === 'pre_restore'" class="chip chip-neutral"
                    :title="$t('admin.backupView.automatischVorEinerWiederherstellung')">
                {{ $t('admin.backupView.sicherheitskopie') }}
              </span>
            </td>
            <td>{{ formatDate(b.created_at) }}</td>
            <td>{{ formatSize(b.size_bytes) }}</td>
            <td>
              <template v-if="b.format === 2 && b.inhalt">
                <span class="zahlen-zelle">{{ inhaltText(b.inhalt) }}</span>
                <span v-if="b.app_version" class="meta-klein">{{ $t('admin.backupView.versionV0', { v0: b.app_version }) }}</span>
              </template>
              <span v-else-if="b.format === 1" class="chip chip-warn"
                    :title="$t('admin.backupView.archivAusDerSQLiteZeitEnthaltDenInha')">
                {{ $t('admin.backupView.altesFormatOhneDatenbank') }}
              </span>
              <span v-else class="chip chip-danger">{{ $t('admin.backupView.nichtLesbar') }}</span>
            </td>
            <td class="action-cell">
              <button class="btn-secondary" @click="onDownload(b.id)"
                      :disabled="downloading === b.id">
                {{ downloading === b.id ? $t('admin.backupView.lade') : $t('admin.backupView.herunterladen') }}
              </button>
              <button class="btn-secondary" @click="onUebernehmen(b.id)"
                      :disabled="restoring !== null || b.format !== 2"
                      :title="$t('admin.backupView.mandantenAusDiesemArchivEinfugenOhne')">
                {{ $t('admin.backupView.ubernehmen') }}
              </button>
              <button class="btn-warn" @click="onRestore(b.id)"
                      :disabled="restoring !== null">
                {{ restoring === b.id ? $t('admin.backupView.stelleWiederHer') : $t('admin.backupView.wiederherstellen') }}
              </button>
              <button class="btn-danger" @click="onDelete(b.id)"
                      :disabled="restoring !== null">{{ $t('common.delete') }}</button>
            </td>
          </tr>
          <tr v-if="!admin.loading && admin.backups.length === 0">
            <td colspan="5" class="empty">{{ $t('admin.backupView.keineSicherungenVorhanden') }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Wiederherstellen: erst zeigen, was drinsteckt, dann fragen -->
    <div v-if="confirmRestore" class="modal-overlay" @mousedown.self="closeConfirm">
      <div class="modal-content" role="dialog" aria-modal="true">
        <h3>{{ $t('admin.backupView.sicherungWiederherstellen') }}</h3>
        <p class="modal-intro">
          {{ $t('admin.backupView.archiv') }} <code>{{ confirmRestore }}</code> {{ $t('admin.backupView.wirdEingespieltVorDemEinspielenLegtD') }}
        </p>

        <p v-if="inhaltLaden" class="laden">{{ $t('admin.backupView.archivWirdGelesen') }}</p>

        <template v-else-if="inhalt">
          <div class="inhalt-box">
            <div class="inhalt-zeile">
              <span class="label">{{ $t('common.format') }}</span>
              <span>{{ formatArchivformat(inhalt.format) }}</span>
            </div>
            <div class="inhalt-zeile">
              <span class="label">{{ $t('common.erstelltAm') }}</span>
              <span>{{ formatDate(inhalt.created_at) }}</span>
            </div>
            <div class="inhalt-zeile" v-if="inhalt.app_version">
              <span class="label">{{ $t('admin.backupView.suiteVersion') }}</span>
              <span>{{ inhalt.app_version }}</span>
            </div>
            <div class="inhalt-zeile">
              <span class="label">{{ $t('admin.backupView.datenbank') }}</span>
              <span>
                {{ $t('admin.backupView.v0TabellenV1', { v0: nf(inhalt.tabellen), v1: inhalt.zeilen == null ? $t('admin.backupView.zeilenzahlNichtVermerkt') : nf(inhalt.zeilen) + $t('admin.backupView.zeilen') }) }}
              </span>
            </div>
            <div class="inhalt-zeile">
              <span class="label">{{ $t('admin.backupView.dateien') }}</span>
              <span>{{ nf(inhalt.dateien) }}</span>
            </div>
          </div>

          <div v-if="inhaltWarnungen.length" class="warn-block prominent">
            <div class="warn-kopf">{{ $t('admin.backupView.vorDemEinspielenBeachten') }}</div>
            <ul class="warn-liste scrollbar">
              <li v-for="(w, i) in inhaltWarnungen" :key="i">{{ w }}</li>
            </ul>
          </div>
        </template>

        <p v-else class="laden">
          {{ $t('admin.backupView.derInhaltDesArchivsKonnteNichtGelese') }}
        </p>

        <!-- #1813: Was ersetzt wird, entscheidet der Betreiber. Vorausgewählt
             ist „nur Fachdaten": Ein Archiv stammt oft von einer anderen
             Installation, und die Konten gehören zur Installation, nicht zu
             den Daten. Wer das übersieht, sperrt sich aus. -->
        <fieldset class="umfang">
          <legend>{{ $t('admin.backupView.wasSollEingespieltWerden') }}</legend>
          <label class="umfang-option">
            <input type="radio" value="fachdaten" v-model="umfang" />
            <span>
              <strong>{{ $t('admin.backupView.nurFachdaten') }}</strong> {{ $t('admin.backupView.firmenProjekteBewertungenNachweise') }}
              <em>{{ $t('admin.backupView.benutzerkontenRollenPasskeysUndDerRe') }}</em>
            </span>
          </label>
          <label class="umfang-option">
            <input type="radio" value="alles" v-model="umfang" />
            <span>
              <strong>{{ $t('admin.backupView.fachdatenUndBenutzer') }}</strong> {{ $t('admin.backupView.vollstandigerStandDesArchivs') }}
              <em>{{ $t('admin.backupView.furDenWiederanlaufDerselbenInstallat') }}</em>
            </span>
          </label>
          <label class="umfang-option">
            <input type="radio" value="nur_benutzer" v-model="umfang" />
            <span>
              <strong>{{ $t('admin.backupView.nurBenutzer') }}</strong> {{ $t('admin.backupView.ausschliesslichKontenUndRollen') }}
              <em>{{ $t('admin.backupView.etwaUmZugangeAusEinerSicherungZuruck') }}</em>
            </span>
          </label>
        </fieldset>

        <!-- #1809: „Sind Sie sicher?" ohne Zahlen ist keine Warnung. -->
        <div v-if="vorschauLaden" class="laden">{{ $t('admin.backupView.abgleichMitDemAktuellenStand') }}</div>
        <div v-else-if="vorschau" class="vorschau">
          <div class="vorschau-kopf">
            {{ $t('admin.backupView.wasSichAndert') }}
            <span v-if="vorschau.verlust_gesamt > 0" class="verlust-marke">
              {{ $t('admin.backupView.v0DatensatzeWerdenEntfernt', { v0: nf(vorschau.verlust_gesamt) }) }}
            </span>
            <span v-else class="kein-verlust">{{ $t('admin.backupView.keinDatenverlustErkennbar') }}</span>
          </div>
          <table class="vorschau-tabelle">
            <thead>
              <tr><th>{{ $t('common.bereich') }}</th><th>{{ $t('admin.backupView.imArchiv') }}</th><th>aktuell</th><th>{{ $t('admin.backupView.folge') }}</th></tr>
            </thead>
            <tbody>
              <tr v-for="z in vorschauZeilen" :key="z.schema + z.tabelle"
                  :class="{ verlust: z.verlust > 0, unberuehrt: !z.betroffen }">
                <td>{{ z.bezeichnung }}</td>
                <td>{{ z.im_archiv == null ? '—' : nf(z.im_archiv) }}</td>
                <td>{{ z.im_ziel == null ? '—' : nf(z.im_ziel) }}</td>
                <td>
                  <template v-if="!z.betroffen">{{ $t('admin.backupView.bleibtUnverandert') }}</template>
                  <template v-else-if="z.verlust > 0">
                    {{ $t('admin.backupView.v0WerdenEntfernt', { v0: nf(z.verlust) }) }}
                  </template>
                  <template v-else>{{ $t('admin.backupView.wirdErsetzt') }}</template>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="vorschau.installation_unberuehrt" class="hinweis-zeile">
            {{ $t('admin.backupView.kontenRollenPasskeysUndDerRevisionsp') }}
          </p>
        </div>

        <p class="warnsatz" v-if="umfang === 'alles'">
          {{ $t('admin.backupView.derAktuelleDatenbestandWirdUberschri') }}
        </p>
        <p class="warnsatz" v-else>{{ $t('admin.backupView.dieBetroffenenBestandeWerdenUberschr') }}</p>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeConfirm">{{ $t('common.cancel') }}</button>
          <button class="btn-danger" @click="executeRestore" :disabled="inhaltLaden">
            {{ $t('admin.backupView.bestatigenUndWiederherstellen') }}
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
        <h3>{{ $t('admin.backupView.datenAusEinemAnderenStandUbernehmen') }}</h3>
        <p class="modal-intro">
          {{ $t('admin.backupView.aus') }} <code>{{ confirmUebernahme }}</code> {{ $t('admin.backupView.werdenDieAusgewahltenMandanten') }}
          <strong>{{ $t('admin.backupView.eingefugt') }}</strong>{{ $t('admin.backupView.derVorhandeneBestandDieserInstallati') }}
        </p>

        <div v-if="mandantenLaden" class="laden">{{ $t('admin.backupView.archivWirdGelesen2') }}</div>
        <template v-else-if="archivMandanten.length">
          <div class="auswahl-kopf">
            <label class="umfang-option">
              <input type="checkbox" :checked="alleGewaehlt"
                     @change="alleUmschalten(($event.target as HTMLInputElement).checked)" />
              <span>{{ $t('admin.backupView.alleV0Mandanten', { v0: archivMandanten.length }) }}</span>
            </label>
            <span class="meta-klein">{{ $t('admin.backupView.v0Ausgewahlt', { v0: gewaehlt.length }) }}</span>
          </div>

          <table class="vorschau-tabelle">
            <thead>
              <tr><th></th><th>{{ $t('common.mandant') }}</th><th>{{ $t('admin.backupView.projekteImArchiv') }}</th><th>{{ $t('admin.backupView.hierSchonVorhanden') }}</th></tr>
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
                        :title="$t('admin.backupView.derMandantIstHierAlsGeloschtMarkiert')">
                    {{ $t('admin.backupView.geloscht') }}
                  </span>
                  <span v-else class="chip chip-neutral">nein</span>
                </td>
              </tr>
            </tbody>
          </table>

          <fieldset class="umfang" v-if="kollisionen.length">
            <legend>{{ $t('admin.backupView.v0AusgewahlteMandantenGibtEsHierScho', { v0: kollisionen.length }) }}</legend>
            <label class="umfang-option">
              <input type="radio" value="behalten" v-model="beiKollision" />
              <span>
                <strong>{{ $t('admin.backupView.bestandBehalten') }}</strong> {{ $t('admin.backupView.dieseMandantenWerdenUbersprungenDerH') }}
              </span>
            </label>
            <label class="umfang-option">
              <input type="radio" value="ersetzen" v-model="beiKollision" />
              <span>
                <strong>{{ $t('admin.backupView.durchDenStandAusDemArchivErsetzen') }}</strong> {{ $t('admin.backupView.dieDatenDieserMandantenWerdenHierEnt') }}
              </span>
            </label>
          </fieldset>

          <label class="umfang-option">
            <input type="checkbox" v-model="mitBenutzern" />
            <span>
              {{ $t('admin.backupView.benutzerkontenGruppenUndMitgliedscha') }}
            </span>
          </label>

          <p class="hinweis-zeile">
            {{ $t('admin.backupView.hochgeladeneDateienDerUbernommenenDa') }}
          </p>

          <div v-if="probe" class="vorschau">
            <div class="vorschau-kopf">
              <strong>{{ $t('admin.backupView.probelauf') }}</strong>
              <span class="verlust-marke neutral">
                {{ $t('admin.backupView.v0ZeilenInV1Tabellen', { v0: nf(probe.zeilen), v1: nf(probe.tabellen) }) }}
              </span>
            </div>
            <p v-if="probe.uebersprungen?.length" class="hinweis-zeile">
              {{ $t('admin.backupView.ubersprungenV0', { v0: probe.uebersprungen.join(', ') }) }}
            </p>
            <ul v-if="probeWarnungen.length" class="warn-liste">
              <li v-for="(w, i) in probeWarnungen" :key="i">{{ w }}</li>
            </ul>
          </div>
        </template>
        <p v-else class="warnsatz">
          {{ $t('admin.backupView.dasArchivEnthaltKeineUbernehmbarenMa') }}
        </p>

        <div class="modal-actions">
          <button class="btn-secondary" @click="closeUebernahme">{{ $t('common.cancel') }}</button>
          <button class="btn-secondary" @click="executeUebernahme(true)"
                  :disabled="!gewaehlt.length || uebernehmend">
            {{ $t('admin.backupView.probelauf') }}
          </button>
          <button class="btn-warn" @click="executeUebernahme(false)"
                  :disabled="!gewaehlt.length || uebernehmend">
            {{ uebernehmend ? $t('admin.backupView.ubernehme') : $t('admin.backupView.ubernehmen2') }}
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
import { t } from '../../i18n'

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
  if (!i) return t('admin.backupView.inhaltNichtVermerkt')
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
  if (f === 2) return t('admin.backupView.formatVollstandigeSicherung')
  if (f === 1) return t('admin.backupView.formatAltesFormatOhneDatenbankinhalt')
  return t('admin.backupView.formatUnbekannt')
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
    admin.error = t('admin.backupView.nurZipDateienWerdenAngenommen')
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
      + t('admin.backupView.dasFormatStehtInDerSpalteInhalt')
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
      + t('admin.backupView.andereMandantenSindNichtBetroffenVor')
      + t('admin.backupView.sicherheitskopieDesAktuellenStandsAn'))) return
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
    hinweis: t('admin.backupView.dieUbernommenenMandantenStehenJetztN')
           + t('admin.backupView.bestandNichtsWurdeGeloscht'),
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
