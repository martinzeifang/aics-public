<!--
  RequirementActions — KI-Bewertung + Issues an einer Anforderung bzw. einer
  OWASP-Kontrolle (CRA, NIS2, AI Act, DSGVO).

  Seit #1847/#1848 setzt diese Datei nur noch zusammen: `KiBewertungsBlock`
  und `IssueVerknuepfung` sind geteilte Bausteine, und **sie sind aus dieser
  Datei entstanden** — sie war die reifste der fünf Fassungen. Darum war die
  Richtung „extrahieren, nicht neu schreiben" die richtige: Für die vier
  Anforderungs-Module ändert sich nichts (gleiche Endpunkte, gleiche
  Reihenfolge), und die vier übrigen Masken erben, was hier über zwanzig
  Issues gewachsen ist — Daten-Vorschau mit Egress-Tor (#868/#1840),
  Hinweis-Feld samt gespeicherten Projekt-Hinweisen (#1834/#1835),
  Herkunftsnachweis (#1765), Abbruch (#1836/E1).

  Was dabei an Zeilen verschwunden ist, war nicht Logik, sondern Wiederholung:
  vier Modal-Gerüste mit eigenem Overlay-CSS (jetzt `ModalRahmen`, #1849) und
  die Beschriftungen, die in fünf Masken auseinanderliefen (jetzt
  `utils/aktionen.ts`, #1851).
-->
<template>
  <!-- #1765: Herkunfts-/Prüfhinweis direkt unter Bewertung + Kommentar — der
       Vorbehalt gehört an den Text, nicht in das gedruckte Dokument. -->
  <KiHerkunftBadge
    v-if="requirement?.id && projektName"
    :modul="kiModul"
    :projekt="projektName"
    :art="kiArt"
    :objekt-id="requirement.id"
  />

  <!-- #1564: Risiko für Nichterfüllung → verknüpfte Risikobewertung -->
  <RequirementRiskLinks
    v-if="requirement?.id && projektName"
    :api-base="apiBase"
    :projekt-name="projektName"
    :object-kind="objectKind || 'requirement'"
    :object-id="String(requirement.id)"
    :titel="requirement.titel || requirement.title || ''"
    :score="requirement.bewertung ?? requirement.score ?? requirement.status ?? null"
    :kommentar="requirement.kommentar || requirement.notes || ''"
  />

  <KiBewertungsBlock
    v-if="requirement?.id"
    :adapter="kiAdapter"
    :projekt-name="projektName"
    :objekt="requirement"
    :objekt-id="requirement.id"
    :objekt-titel="objektTitel"
    :issues="issues"
    :freitext="freitext"
    :mit-herkunft-badge="false"
    @gespeichert="(d: any) => emit('saved', d)"
    @fehler="(m: string) => emit('error', m)"
  />

  <IssueVerknuepfung
    v-if="requirement?.id"
    ref="issueBlock"
    :api-base="apiBase"
    :projekt-name="projektName"
    :objekt-pfad="objektPfad"
    :objekt-id="requirement.id"
    :objekt-titel="String(requirement.id)"
    :repo-vorschlag="defaultRepo || ''"
    text-ziel="den Kommentar"
    @geaendert="aufIssueAenderung"
    @uebernommen="(d: any) => emit('saved', d)"
  />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import KiHerkunftBadge from './KiHerkunftBadge.vue'
import IssueVerknuepfung from './IssueVerknuepfung.vue'
import KiBewertungsBlock from './KiBewertungsBlock.vue'
import RequirementRiskLinks from './RequirementRiskLinks.vue'
import { anforderungKiAdapter } from '../../utils/kiBewertung'
import { useKiHerkunftStore, type KiArt } from '../../stores/kiHerkunft'

const props = defineProps<{
  /** Aktuelle Anforderung (mit id, titel, kapitel) */
  requirement: any
  /** Projekt-Name für API-URL */
  projektName: string
  /** API-Base-URL: /cra | /nis2 | /aiact | /dsgvo */
  apiBase: string
  /** Object-Kind für Issue-Linking: 'requirement' (default) | 'owasp' */
  objectKind?: 'requirement' | 'owasp'
  /** Default-Repo aus Projekt-Meta-JSON */
  defaultRepo?: string
}>()

const emit = defineEmits<{
  /** Wird ausgelöst wenn Bewertung erfolgreich übernommen wurde */
  saved: [result: any]
  error: [message: string]
}>()

const issueBlock = ref<InstanceType<typeof IssueVerknuepfung> | null>(null)

// #1765: Das Modul steckt bereits in `apiBase` (/cra, /nis2, /aiact, /dsgvo) —
// genau das URL-Segment, über das auch das Herkunfts-Register adressiert wird.
const kiHerkunft = useKiHerkunftStore()
const kiModul = computed(() => props.apiBase.replace(/^\/+|\/+$/g, ''))
const kiArt = computed<KiArt>(() => (props.objectKind === 'owasp' ? 'owasp' : 'requirement'))

const objektPfad = computed(() => (props.objectKind === 'owasp' ? 'owasp' : 'anforderungen'))
const kiAdapter = computed(() =>
  anforderungKiAdapter(props.apiBase, props.projektName,
                       props.objectKind === 'owasp' ? 'owasp' : 'anforderungen'))

const objektTitel = computed(() => {
  const titel = props.requirement?.titel || props.requirement?.title
  return `${props.requirement?.id || ''}${titel ? `: ${titel}` : ''}`
})

/** Der Freitext, der die Markierung „⚠️ Neubewertung erforderlich" trägt. */
const freitext = computed(() =>
  String(props.requirement?.kommentar ?? props.requirement?.notiz ?? ''))

/** Die verknüpften Issues für die Transparenz der Neubewertung (#1527). */
const issues = computed<any[]>(() => issueBlock.value?.issues || [])

/**
 * Der Abgleich kann „⚠️ Neubewertung erforderlich" in den Kommentar
 * geschrieben haben (#1850) — ohne Nachladen stünde die Markierung in der
 * Datenbank und nicht auf dem Schirm.
 */
const aufIssueAenderung = (ergebnis: any) => {
  emit('saved', ergebnis)
  if (props.requirement?.id && props.projektName) {
    kiHerkunft.reload(kiModul.value, props.projektName, kiArt.value)
  }
}
</script>
