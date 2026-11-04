/**
 * #1834 — eigene Hinweise an einem angezeigten Prompt.
 *
 * Masken, die einen Prompt **zeigen** (zum Kopieren oder zum direkten Lauf),
 * brauchen zweierlei: das Feld für den Hinweis und einen angezeigten Text, der
 * dem entspricht, was gesendet wird. Zusammengesetzt wird deshalb
 * serverseitig über `POST /api/ai/prompt/komponieren` — dieselbe Funktion, die
 * auch beim Senden zusammensetzt.
 *
 * Im Frontend anzuhängen wäre die naheliegende Abkürzung und die zweite
 * Zusammenbau-Stelle: Zwei Fassungen desselben Prompts laufen auseinander, und
 * auffallen würde es erst, wenn jemand eine KI-Antwort nicht mehr erklären
 * kann. Dieselbe Fehlerklasse wie die Spiegel-Listen aus #1727/#1735.
 *
 * Masken, die den Prompt NICHT zeigen (Auto-Bewertung, Massenlauf,
 * Dokument-Check, Zusammenfassung), brauchen das hier nicht — sie legen den
 * Hinweis als `prompt_zusatz` in den Body ihres Streams, und
 * `shared/sse.stream_ai_sse` setzt ihn ein.
 */
import { ref, watch, type Ref } from 'vue'
import apiClient from '../api/client'

export interface PromptZusatz {
  /** Der eingetippte Hinweis (v-model für PromptZusatzFeld). */
  zusatz: Ref<string>
  /** Der anzuzeigende/zu kopierende Prompt — Basis plus Hinweis. */
  anzeigePrompt: Ref<string>
  /** Gesetzt, wenn der Hinweis NICHT eingesetzt werden konnte. */
  fehler: Ref<string>
  /** Längengrenze, vom Server bestätigt (shared/prompt_zusatz.GRENZE). */
  grenze: Ref<number>
}

/**
 * @param basis  Funktion, die den unveränderten Prompt liefert (reaktiv gelesen).
 * @param verzug Entprellung in Millisekunden; 0 schaltet sie ab (Tests).
 */
export function usePromptZusatz(basis: () => string, verzug = 600): PromptZusatz {
  const zusatz = ref('')
  const fehler = ref('')
  const grenze = ref(2000)
  const anzeigePrompt = ref(basis())
  let timer: ReturnType<typeof setTimeout> | null = null

  async function komponieren() {
    fehler.value = ''
    const roh = basis()
    if (!zusatz.value.trim() || !roh) { anzeigePrompt.value = roh; return }
    try {
      const res = await apiClient.post('/ai/prompt/komponieren',
                                       { prompt: roh, prompt_zusatz: zusatz.value })
      anzeigePrompt.value = res.data?.prompt || roh
      if (res.data?.grenze) grenze.value = res.data.grenze
    } catch (e: any) {
      // Still zu scheitern wäre hier besonders schlecht: Der Anwender kopiert
      // dann einen Prompt, in dem seine Ergänzung fehlt, und merkt es erst an
      // der Antwort.
      anzeigePrompt.value = roh
      fehler.value = 'Der Hinweis konnte nicht eingesetzt werden — der '
        + 'angezeigte Prompt enthält ihn nicht. '
        + (e?.response?.data?.error || e?.message || '')
    }
  }

  watch(zusatz, () => {
    if (!verzug) { komponieren(); return }
    if (timer) clearTimeout(timer)
    timer = setTimeout(komponieren, verzug)
  })
  // Holt der Aufrufer einen neuen Prompt, gilt der Hinweis weiter.
  watch(basis, () => { komponieren() })

  return { zusatz, anzeigePrompt, fehler, grenze }
}
