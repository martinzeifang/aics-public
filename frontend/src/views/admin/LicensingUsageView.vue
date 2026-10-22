<template>
  <div class="licensing-view">
    <h1>🧾 Mandanten &amp; Abrechnung</h1>
    <p class="intro">
      Abrechnungsgrundlage im MSP-/Wholesale-Modell: je Mandant ein Grundpreis plus die
      gebuchten Zusatzmodule. Ein Mandant ist <strong>abrechnungsrelevant</strong>, sobald
      in mindestens einem Modul ein Projekt existiert — angelegte, aber nie bespielte
      Mandanten kosten nichts.
    </p>

    <div class="tabs" role="tablist">
      <button v-for="t in tabs" :key="t.id" :class="['tab', { active: tab === t.id }]"
              role="tab" :aria-selected="tab === t.id" @click="tab = t.id">{{ t.label }}</button>
    </div>

    <div v-if="fehler" class="alert">{{ fehler }}</div>

    <!-- ══════════ Abrechnung ══════════ -->
    <template v-if="tab === 'abrechnung'">
      <div v-if="ladeUsage" class="hint">⏳ Lade Mandanten …</div>
      <template v-else-if="usage">
        <div class="kpi-grid">
          <div class="kpi">
            <span class="kpi-wert">{{ usage.summe.mandanten_aktiv }}</span>
            <span class="kpi-label">abrechnungsrelevant</span>
            <span class="kpi-sub">von {{ usage.summe.mandanten_gesamt }} angelegt</span>
          </div>
          <div class="kpi">
            <span class="kpi-wert">{{ geld(usage.summe.monatspreis) }}</span>
            <span class="kpi-label">pro Monat</span>
            <span class="kpi-sub">
              Liste {{ geld(usage.summe.listenpreis_monat) }}
              <template v-if="usage.summe.rabatt_prozent">
                · Staffel −{{ usage.summe.rabatt_prozent }} %
              </template>
            </span>
          </div>
          <div class="kpi">
            <span class="kpi-wert">{{ geld(usage.summe.jahrespreis) }}</span>
            <span class="kpi-label">pro Jahr</span>
            <span class="kpi-sub">hochgerechnet</span>
          </div>
          <div class="kpi" :class="{ warn: usage.summe.mandanten_ruhend > 0 }">
            <span class="kpi-wert">{{ usage.summe.mandanten_ruhend }}</span>
            <span class="kpi-label">ruhend</span>
            <span class="kpi-sub">&gt; {{ usage.definition.inaktiv_ab_tagen }} Tage ohne Änderung</span>
          </div>
        </div>

        <div class="toolbar">
          <input v-model="suche" type="search" placeholder="🔍 Mandant suchen …"
                 aria-label="Mandanten durchsuchen" />
          <label class="check">
            <input type="checkbox" v-model="nurAktive" /> nur abrechnungsrelevante
          </label>
          <span class="spacer"></span>
          <button class="btn-secondary" @click="ladeAlles">🔄 Aktualisieren</button>
          <button class="btn-primary" @click="csvHerunterladen" :disabled="csvLaeuft">
            {{ csvLaeuft ? '⏳ …' : '⬇ CSV für die Abrechnung' }}
          </button>
        </div>

        <p v-if="usage.lizenz_module_abrechenbar.length < 4" class="hint">
          ℹ️ Diese Lizenz umfasst die Zusatzmodule
          <strong>{{ usage.lizenz_module_abrechenbar.map(label).join(', ') || '—' }}</strong>.
          Module, die ein Mandant gebucht hat, die Lizenz aber nicht abdeckt, erscheinen als
          <em>nicht lizenziert</em> und werden nicht berechnet.
        </p>

        <table class="tabelle">
          <thead>
            <tr>
              <th>Mandant</th>
              <th>Module</th>
              <th class="num">Projekte</th>
              <th class="num">Letzte Änderung</th>
              <th class="num">Monatspreis</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in gefilterteMandanten" :key="m.name"
                :class="{ inaktiv: !m.aktiv, ruhend: m.ruhend }">
              <td>
                <div class="m-name">{{ m.name }}</div>
                <div class="m-sub">
                  {{ m.unternehmen || '—' }}
                  <template v-if="m.berater"> · {{ m.berater }}</template>
                </div>
              </td>
              <td>
                <span v-for="mod in m.module_gebucht" :key="mod" class="badge">{{ label(mod) }}</span>
                <span v-for="mod in m.module_nicht_lizenziert" :key="`nl-${mod}`"
                      class="badge warn" title="Von der Lizenz nicht abgedeckt — nicht berechnet">
                  {{ label(mod) }} ⚠
                </span>
              </td>
              <td class="num">{{ m.projekte_gesamt }}</td>
              <td class="num">
                {{ datum(m.letzte_aktivitaet) }}
                <span v-if="m.ruhend" class="pill">ruhend</span>
                <span v-else-if="!m.aktiv" class="pill grau">kein Projekt</span>
              </td>
              <td class="num geld">{{ m.aktiv ? geld(m.preis.monatspreis) : '—' }}</td>
            </tr>
            <tr v-if="gefilterteMandanten.length === 0">
              <td colspan="5" class="hint">Kein Mandant passt zum Filter.</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th colspan="4">Summe ({{ usage.summe.mandanten_aktiv }} abrechnungsrelevant)</th>
              <th class="num geld">{{ geld(usage.summe.monatspreis) }}</th>
            </tr>
          </tfoot>
        </table>

        <details v-if="waisenListe.length" class="waisen">
          <summary>⚠ {{ waisenListe.length }} Projekt(e) ohne Mandantenzuordnung</summary>
          <p class="hint">
            Diese Projekte zählen keinem Mandanten zu und fehlen damit in der Abrechnung.
            Im Reiter „Mandantenfähigkeit" lassen sie sich zuordnen.
          </p>
          <ul>
            <li v-for="w in waisenListe" :key="`${w.modul}-${w.projekt}`">
              <strong>{{ label(w.modul) }}:</strong> {{ w.projekt }}
            </li>
          </ul>
        </details>
      </template>
    </template>

    <!-- ══════════ Preisblatt ══════════ -->
    <section v-else-if="tab === 'preisblatt'" class="card">
      <h2>Preisblatt</h2>
      <p class="hint">
        Netto-Monatspreise je Mandant. Ein Modul mit Einzelpreis <code>0</code> ist
        <strong>im Grundpreis enthalten</strong> und erscheint nicht als Posten.
        Das gilt für <strong>WiBA</strong>: Grundpreis-Modul, lizenzseitig immer dabei —
        wie die Risikobewertung — und <strong>ohne Aufpreis</strong>. Ausblenden lässt es
        sich unter <em>Einstellungen → Module</em>; das ändert weder Lizenz noch Preis.
      </p>
      <div v-if="ladePreise" class="hint">⏳ Lade …</div>
      <template v-else-if="preisDraft">
        <div class="preis-grid">
          <label>Grundpreis
            <input type="number" min="0" step="5" v-model.number="preisDraft.grundpreis" />
          </label>
          <label v-for="mod in preisModule" :key="mod">{{ label(mod) }}
            <input type="number" min="0" step="5" v-model.number="preisDraft.module[mod]" />
          </label>
          <label>Währung
            <input v-model="preisDraft.waehrung" maxlength="8" />
          </label>
        </div>

        <h3>Mengenstaffel</h3>
        <div v-for="(stufe, i) in preisDraft.staffel" :key="i" class="staffel-row">
          <span>ab</span>
          <input type="number" min="1" v-model.number="stufe.ab" />
          <span>Mandanten</span>
          <input type="number" min="0" max="100" step="1" v-model.number="stufe.rabatt" />
          <span>% Rabatt</span>
          <button class="btn-small" @click="preisDraft.staffel.splice(i, 1)">entfernen</button>
        </div>
        <button class="btn-small" @click="preisDraft.staffel.push({ ab: 1, rabatt: 0 })">
          + Stufe
        </button>

        <div class="vorschau">
          <strong>Vorschau:</strong>
          nur Grundpreis {{ geld(preisDraft.grundpreis) }} ·
          alle Module {{ geld(vollpreis) }}
        </div>

        <div class="row">
          <button class="btn-primary" :disabled="speichert" @click="preisblattSpeichern">
            {{ speichert ? '⏳ …' : '💾 Speichern' }}
          </button>
          <button class="btn-secondary" @click="preisblattZuruecksetzen">↺ Default</button>
          <span v-if="preisMsg" class="ok">{{ preisMsg }}</span>
        </div>
      </template>
    </section>

    <!-- ══════════ Mandantenfähigkeit ══════════ -->
    <section v-else class="card">
      <h2>Mandantenfähigkeit</h2>
      <p class="hint">
        Prüft, ob jedes Modulprojekt eindeutig einem Mandanten gehört. Nur zugeordnete
        Projekte erscheinen im Risiko-Cockpit, in der Abrechnung und in der
        Firmen-Zugriffsbeschränkung einzelner Nutzer.
      </p>
      <div v-if="ladeTenancy" class="hint">⏳ Prüfe …</div>
      <template v-else-if="tenancy">
        <div class="score" :class="scoreKlasse">
          <span class="score-wert">{{ tenancy.score_prozent }} %</span>
          <span class="score-label">
            {{ tenancy.projekte_mit_firmen_id }} von {{ tenancy.projekte_gesamt }}
            Projekten mit harter Mandanten-Verknüpfung
          </span>
        </div>

        <p v-if="tenancy.befunde.length === 0" class="ok">
          ✓ Keine Befunde — alle Projekte sind einem Mandanten zugeordnet.
        </p>
        <ul v-else class="befunde">
          <li v-for="(b, i) in tenancy.befunde" :key="i" :class="b.schwere">
            <span class="schwere-pill">{{ b.schwere === 'hoch' ? 'hoch' : 'mittel' }}</span>
            {{ b.text }}
          </li>
        </ul>

        <div class="row">
          <button class="btn-secondary" @click="ladeTenancyReport">🔄 Neu prüfen</button>
          <router-link to="/admin/firmen-link" class="btn-primary">
            → Zur Firmen-Zuordnung
          </router-link>
        </div>
        <p class="hint">{{ tenancy.hinweis }}</p>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * Mandanten- und Abrechnungsübersicht (#1706/#1711).
 *
 * Drei Reiter: die monatliche Abrechnungsgrundlage je Mandant (inkl. CSV für die
 * Rechnungsstellung), das konfigurierbare Preisblatt und die
 * Mandantenfähigkeits-Selbstprüfung.
 */
import { computed, onMounted, ref } from 'vue'
import apiClient from '../../api/client'
import { matchesSuche } from '../../composables/useSidebarFilter'

type TabId = 'abrechnung' | 'preisblatt' | 'tenancy'

const tabs: { id: TabId; label: string }[] = [
  { id: 'abrechnung', label: '🧾 Abrechnung' },
  { id: 'preisblatt', label: '💶 Preisblatt' },
  { id: 'tenancy', label: '🏢 Mandantenfähigkeit' },
]

const LABELS: Record<string, string> = {
  cra: 'CRA', nis2: 'NIS2', aiact: 'EU AI Act', dsgvo: 'DSGVO', wiba: 'WiBA',
  risikobewertung: 'Risikobewertung', pentest: 'Pentest', gutachten: 'Gutachten',
  soc: 'SOC', firmen: 'Firmen',
}

const tab = ref<TabId>('abrechnung')
const fehler = ref('')

const usage = ref<any>(null)
const ladeUsage = ref(true)
const suche = ref('')
const nurAktive = ref(false)
const csvLaeuft = ref(false)

const preisDraft = ref<any>(null)
const preisDefault = ref<any>(null)
const preisModule = ref<string[]>([])
const ladePreise = ref(true)
const speichert = ref(false)
const preisMsg = ref('')

const tenancy = ref<any>(null)
const ladeTenancy = ref(true)

const label = (key: string) => LABELS[key] || key

const geld = (v: number | undefined): string => {
  const waehrung = usage.value?.summe?.waehrung || preisDraft.value?.waehrung || 'EUR'
  const n = Number(v ?? 0)
  try {
    return n.toLocaleString('de-DE', { style: 'currency', currency: waehrung,
                                       maximumFractionDigits: 2 })
  } catch {
    return `${n.toFixed(2)} ${waehrung}`
  }
}

const datum = (iso?: string): string => {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? String(iso).slice(0, 10) : d.toLocaleDateString('de-DE')
}

const gefilterteMandanten = computed(() => {
  const liste = (usage.value?.mandanten || []) as any[]
  return liste.filter((m) =>
    (!nurAktive.value || m.aktiv) &&
    matchesSuche(suche.value, m.name, m.unternehmen, m.berater))
})

const waisenListe = computed(() => {
  const out: { modul: string; projekt: string }[] = []
  const waisen = usage.value?.waisen || {}
  for (const modul of Object.keys(waisen)) {
    for (const projekt of waisen[modul] || []) out.push({ modul, projekt })
  }
  return out
})

const vollpreis = computed(() => {
  if (!preisDraft.value) return 0
  const mods = Object.values(preisDraft.value.module || {}) as number[]
  return Number(preisDraft.value.grundpreis || 0) +
    mods.reduce((s, v) => s + Number(v || 0), 0)
})

const scoreKlasse = computed(() => {
  const s = Number(tenancy.value?.score_prozent ?? 0)
  return s >= 95 ? 'gruen' : s >= 75 ? 'gelb' : 'rot'
})

async function ladeUsageReport() {
  ladeUsage.value = true
  try {
    const res = await apiClient.get('/admin/licensing/usage')
    usage.value = res.data
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Abrechnungsdaten konnten nicht geladen werden.'
  } finally {
    ladeUsage.value = false
  }
}

async function ladePreisblatt() {
  ladePreise.value = true
  try {
    const res = await apiClient.get('/admin/licensing/preisblatt')
    preisDraft.value = JSON.parse(JSON.stringify(res.data.preisblatt))
    preisDefault.value = res.data.default
    preisModule.value = res.data.module || []
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Preisblatt konnte nicht geladen werden.'
  } finally {
    ladePreise.value = false
  }
}

async function ladeTenancyReport() {
  ladeTenancy.value = true
  try {
    const res = await apiClient.get('/admin/tenancy/report')
    tenancy.value = res.data
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Mandanten-Prüfung fehlgeschlagen.'
  } finally {
    ladeTenancy.value = false
  }
}

async function preisblattSpeichern() {
  speichert.value = true
  preisMsg.value = ''
  try {
    const res = await apiClient.put('/admin/licensing/preisblatt',
                                    { preisblatt: preisDraft.value })
    preisDraft.value = JSON.parse(JSON.stringify(res.data.preisblatt))
    preisMsg.value = '✓ Gespeichert'
    // Preise wirken direkt auf die Abrechnung → Report neu holen.
    await ladeUsageReport()
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'Speichern fehlgeschlagen.'
  } finally {
    speichert.value = false
  }
}

function preisblattZuruecksetzen() {
  if (preisDefault.value) {
    preisDraft.value = JSON.parse(JSON.stringify(preisDefault.value))
    preisMsg.value = 'Default übernommen — noch nicht gespeichert.'
  }
}

async function csvHerunterladen() {
  csvLaeuft.value = true
  try {
    const res = await apiClient.get('/admin/licensing/usage?format=csv',
                                    { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `aics-abrechnung-${usage.value?.stichtag || 'export'}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    fehler.value = e?.response?.data?.error || 'CSV-Export fehlgeschlagen.'
  } finally {
    csvLaeuft.value = false
  }
}

async function ladeAlles() {
  fehler.value = ''
  await Promise.all([ladeUsageReport(), ladePreisblatt(), ladeTenancyReport()])
}

onMounted(ladeAlles)
</script>

<style scoped>
.licensing-view { max-width: 1100px; display: flex; flex-direction: column; gap: 16px; }
h1 { margin: 0; font-size: 22px; }
.intro { margin: 0; font-size: 13px; color: #666; line-height: 1.5; }

.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--color-border, #e0e0e0); }
.tab {
  border: none; background: none; padding: 8px 14px; cursor: pointer;
  font-size: 13px; color: #666; border-bottom: 2px solid transparent;
}
.tab.active { color: var(--color-primary, #1565c0); border-bottom-color: var(--color-primary, #1565c0); font-weight: 600; }

.card {
  background: white; border: 1px solid var(--color-border, #e0e0e0);
  border-radius: 10px; padding: 16px 18px;
  display: flex; flex-direction: column; gap: 10px;
}
.card h2 { margin: 0; font-size: 16px; }
.card h3 { margin: 8px 0 0; font-size: 13px; color: #555; }

.alert { background: #ffebee; color: #c62828; padding: 10px 12px; border-radius: 6px; font-size: 13px; }
.hint { font-size: 12px; color: #777; margin: 0; line-height: 1.5; }
.ok { color: #2e7d32; font-size: 13px; }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
.kpi {
  background: white; border: 1px solid var(--color-border, #e0e0e0); border-left: 4px solid var(--color-primary, #1565c0);
  border-radius: 8px; padding: 12px 14px; display: flex; flex-direction: column; gap: 2px;
}
.kpi.warn { border-left-color: #ef6c00; }
.kpi-wert { font-size: 22px; font-weight: 700; color: #222; }
.kpi-label { font-size: 12px; font-weight: 600; color: #555; }
.kpi-sub { font-size: 11px; color: #888; }

.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar input[type="search"] {
  padding: 6px 8px; border: 1px solid var(--color-border, #e0e0e0); border-radius: 4px;
  font-size: 13px; min-width: 200px;
}
.check { font-size: 12px; color: #555; display: flex; align-items: center; gap: 5px; }
.spacer { flex: 1; }

.tabelle { width: 100%; border-collapse: collapse; font-size: 13px; background: white;
  border: 1px solid var(--color-border, #e0e0e0); border-radius: 8px; overflow: hidden; }
.tabelle th { text-align: left; padding: 8px 10px; background: #fafafa;
  border-bottom: 2px solid var(--color-border, #e0e0e0); font-size: 11px;
  text-transform: uppercase; letter-spacing: 0.4px; color: #666; }
.tabelle td { padding: 8px 10px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }
.tabelle th.num, .tabelle td.num { text-align: right; white-space: nowrap; }
.tabelle tfoot th { background: #f5f9ff; border-top: 2px solid var(--color-border, #e0e0e0); border-bottom: none; }
.tabelle tr.inaktiv { color: #999; }
.tabelle tr.ruhend { background: #fffdf5; }
.geld { font-variant-numeric: tabular-nums; font-weight: 600; }

.m-name { font-weight: 600; color: #333; }
.m-sub { font-size: 11px; color: #888; margin-top: 2px; }

.badge { display: inline-block; margin: 0 3px 2px 0; padding: 1px 6px; border-radius: 9px;
  background: #e3f2fd; color: #1565c0; font-size: 10px; font-weight: 700; }
.badge.warn { background: #fff3e0; color: #e65100; }

.pill { display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 9px;
  background: #fff3e0; color: #e65100; font-size: 10px; font-weight: 700; }
.pill.grau { background: #eeeeee; color: #757575; }

.waisen { font-size: 12px; }
.waisen summary { cursor: pointer; color: #e65100; font-weight: 600; }
.waisen ul { margin: 6px 0 0; padding-left: 20px; color: #555; }

.preis-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
.preis-grid label { display: flex; flex-direction: column; gap: 3px; font-size: 12px; color: #555; }
.preis-grid input {
  padding: 6px 8px; border: 1px solid var(--color-border, #e0e0e0); border-radius: 4px; font-size: 13px;
}

.staffel-row { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #555; }
.staffel-row input { width: 70px; padding: 4px 6px; border: 1px solid var(--color-border, #e0e0e0); border-radius: 4px; }

.vorschau { font-size: 13px; color: #333; background: #f5f9ff; padding: 8px 10px; border-radius: 6px; }

.row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.score { display: flex; align-items: baseline; gap: 12px; padding: 12px 14px; border-radius: 8px;
  border-left: 4px solid #2e7d32; background: #f1f8e9; }
.score.gelb { border-left-color: #ef6c00; background: #fff8e1; }
.score.rot { border-left-color: #c62828; background: #ffebee; }
.score-wert { font-size: 26px; font-weight: 700; }
.score-label { font-size: 12px; color: #555; }

.befunde { margin: 0; padding-left: 0; list-style: none; display: flex; flex-direction: column; gap: 6px; }
.befunde li { font-size: 13px; color: #444; display: flex; align-items: baseline; gap: 8px; }
.schwere-pill { flex: none; padding: 1px 7px; border-radius: 9px; font-size: 10px; font-weight: 700;
  background: #fff3e0; color: #e65100; text-transform: uppercase; }
.befunde li.hoch .schwere-pill { background: #ffebee; color: #c62828; }

.btn-primary, .btn-secondary, .btn-small {
  padding: 6px 12px; border-radius: 4px; font-size: 13px; cursor: pointer;
  border: 1px solid var(--color-border, #e0e0e0); background: white; text-decoration: none;
}
.btn-primary { background: var(--color-primary, #1565c0); color: white; border-color: transparent; }
.btn-small { padding: 3px 9px; font-size: 11px; }
.btn-primary:disabled, .btn-secondary:disabled { opacity: 0.5; cursor: default; }
</style>
