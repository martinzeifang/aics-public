// Modul-Hilfe Compliance-Audit (#1713).
import type { ModuleHelp } from './types'
import { docsUrl } from './docsUrl'

export const complianceAuditHelp: ModuleHelp = {
  module: 'compliance-audit',
  title: 'Compliance-Audit',
  regulation: 'Framework-abhängig (ISO/IEC 27001, NIS2, CRA, DSGVO, EU AI Act, BSI …)',
  purpose:
    'Das Compliance-Audit erhebt per Fragenkatalog, wie weit eine Organisation ' +
    'gegenüber einem oder mehreren Frameworks tatsächlich ist, und meldet ihr das ' +
    'Ergebnis als Wasserstandsmeldung zurück: vollständig, weitgehend, teilweise ' +
    'oder nicht compliant. Es ist damit die Standortbestimmung am Anfang — nicht ' +
    'die gutachterliche Äußerung am Ende (dafür ist das Gutachten-Modul da).',
  legalBasis: {
    title: 'Abgrenzung und Einordnung',
    intro:
      'Ein Compliance-Audit ist keine gutachterliche Äußerung. Es erhebt den ' +
      'Umsetzungsstand strukturiert und nachvollziehbar, damit Lücken sichtbar ' +
      'werden und priorisiert bearbeitet werden können.',
    bullets: [
      'Die Fragen werden aus den eingelesenen Regulierungstexten (Framework-Bibliothek) erzeugt und bleiben auf die jeweilige Fundstelle bezogen.',
      'Je Frage wird die Erfüllung erfasst: erfüllt, teilweise, nicht erfüllt, nicht anwendbar oder offen.',
      '„Nicht anwendbar" ist eine Scope-Entscheidung des Auditors und fällt aus der Bewertung heraus — sie muss begründbar sein.',
      'Mehrere Frameworks in einem Audit sind möglich; die Stufe wird je Framework und gesamt ausgewiesen.',
      'Das Compliance-Audit gehört zum Grundpreis und ist bei jeder gültigen Lizenz nutzbar — wie die Risikobewertung.',
    ],
  },
  implementation: {
    title: 'Vorgehen im Modul',
    intro:
      'Audit anlegen, Frameworks wählen, Fragen erzeugen, Antworten erheben, ' +
      'Wasserstandsmeldung erstellen. Der Fragebogen kann als XLSX zum Kunden ' +
      'gehen und mit dessen Antworten wieder eingelesen werden.',
    bullets: [
      'Audit anlegen und einer Firma zuordnen (Feld Unternehmen) — die Zuordnung ist Grundlage für Abrechnung und Mandantentrennung.',
      'Framework-Bibliothek füllen: Regulierungstext herunterladen oder als PDF hochladen, anschließend in Abschnitte einlesen.',
      'Fragen erzeugen: Prompt generieren, von der KI beantworten lassen und die Fragen importieren — oder eigene Fragen manuell ergänzen.',
      'Fragebogen als XLSX exportieren, beim Kunden ausfüllen lassen und wieder importieren (der Reimport ordnet die Antworten den Fragen zu).',
      'Erfüllung je Frage setzen. Für Audits aus der Zeit vor v7.4.0 übernimmt „Alte Bewertungen übernehmen" die frühere Freitext-Note einmalig.',
      'Wasserstandsmeldung erstellen: die Stufe wird aus den Antworten berechnet, die KI formuliert nur den Text für den Kunden.',
      'Bei Bedarf aus dem Audit ein Gutachten ableiten (Brücke zum Gutachten-Modul) — die übernommenen Befunde sind bewusst leer und müssen persönlich formuliert werden.',
    ],
  },
  moduleSpecific: {
    title: 'Wie die Stufe zustande kommt',
    intro:
      'Die Compliance-Stufe ist eine Zusage an den Kunden und wird deshalb ' +
      'gerechnet, nicht geschätzt: bei gleichen Antworten kommt immer dieselbe ' +
      'Stufe heraus, und jede Stufe lässt sich Frage für Frage belegen.',
    bullets: [
      'Quote = (1 × erfüllt + 0,5 × teilweise) ÷ (alle Fragen − nicht anwendbare).',
      'Offene Fragen zählen in der Quote wie „nicht erfüllt": Was nicht belegt ist, ist nicht nachgewiesen. Ein Audit mit 10 von 200 beantworteten Fragen kann deshalb nicht „vollständig compliant" ergeben.',
      'Stufen: vollständig = 100 % und nichts offen · weitgehend ab 80 % · teilweise ab 40 % · darunter nicht compliant.',
      'Zusätzlich werden die Quote nur der bewerteten Fragen und die Abdeckung ausgewiesen — so bleibt der Unterschied zwischen „schlecht erfüllt" und „noch nicht erhoben" sichtbar.',
      'Die KI erhält die Stufe als Vorgabe und darf sie nicht ändern; sie begründet sie, nennt die Hauptlücken und schlägt Maßnahmen vor.',
      'Jede Meldung wird mit gerechnetem Stand und KI-Text getrennt archiviert (Verlauf), damit nachvollziehbar bleibt, was gerechnet und was formuliert wurde.',
    ],
  },
  areas: [
    {
      id: 'overview',
      title: '📋 Übersicht',
      zweck: 'Stammdaten des Audits und Auswahl der Frameworks.',
      pflichtfelder: [
        'Name des Audits (eindeutig)',
        'Unternehmen — die geprüfte Firma; ohne Zuordnung fehlt das Audit in Cockpit und Abrechnung',
        'Frameworks — eines oder mehrere; bestimmen, aus welchen Texten Fragen erzeugt werden',
        'Prüfungsfokus — worauf sich das Audit beschränkt (Scope-Abgrenzung)',
      ],
      tipps: [
        'Den Prüfungsfokus eng und schriftlich fassen: er begründet später, warum Fragen als „nicht anwendbar" gelten.',
      ],
    },
    {
      id: 'fragen',
      title: '❓ Fragen',
      zweck: 'Fragenkatalog erzeugen, Antworten und Erfüllung erfassen.',
      pflichtfelder: [
        'Frage mit Bezug zur Fundstelle (Abschnitt/Artikel)',
        'Antwort des Kunden',
        'Erfüllung: erfüllt / teilweise / nicht erfüllt / nicht anwendbar / offen',
        'Kommentar — bei „teilweise" und „nicht erfüllt" die konkrete Lücke',
      ],
      anleitung:
        'Fragen per Prompt erzeugen und importieren, dann als XLSX exportieren, ' +
        'beim Kunden ausfüllen lassen und wieder importieren. Danach je Frage die ' +
        'Erfüllung setzen — sie ist die Grundlage der Stufenberechnung.',
      tipps: [
        '„Nicht anwendbar" sparsam und immer mit Begründung im Kommentar verwenden — es hebt die Quote.',
        'Offene Fragen nicht auf „nicht erfüllt" setzen, nur weil die Antwort fehlt: die Quote behandelt beides gleich, die Abdeckung zeigt aber den Unterschied.',
      ],
    },
    {
      id: 'wasserstand',
      title: '📊 Wasserstand',
      zweck: 'Berechneten Compliance-Stand ansehen und die Kundenmitteilung erzeugen.',
      pflichtfelder: [
        'Erfüllung je Frage gesetzt (sonst ist alles „offen")',
      ],
      anleitung:
        'Stand prüfen, dann die Meldung entweder direkt mit KI erstellen oder den ' +
        'Prompt kopieren und die Antwort einfügen. Die Stufe ändert sich dadurch nicht.',
      tipps: [
        'Vor der Meldung an den Kunden die Abdeckung prüfen: unter etwa 80 % ist die Aussage dünn — das gehört in die Mitteilung.',
        'Der Verlauf zeigt die Entwicklung über die Zeit und eignet sich für Folge-Audits.',
      ],
    },
    {
      id: 'gutachten',
      title: '📄 Bericht',
      zweck: 'Auditbericht als Dokument erzeugen und exportieren.',
      pflichtfelder: ['Ausgewertete Fragen', 'Zusammenfassung', 'Empfehlungen'],
    },
  ],
  links: [
    { label: 'Modul-Dokumentation', href: docsUrl('/modules/compliance-audit/') },
    { label: 'Gutachten-Modul (Ableitung)', href: docsUrl('/modules/gutachten/') },
  ],
}
