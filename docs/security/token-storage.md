# Auth-Token-Storage (#1190)

OWASP ASVS V3 (Session-Management), Secure-by-Design.

## Aktueller Stand (umgesetzt)

- **Zentralisierter Zugriff:** Komponenten lesen das Token NICHT mehr direkt aus
  `sessionStorage`/`localStorage`. Alle Streaming-/SSE-/Download-Flows, die nicht über den
  axios-`apiClient` (Request-Interceptor) laufen, holen das Bearer-Token ausschließlich über
  `frontend/src/api/auth-token.ts` (`bearerToken()` / `authHeader()`).
- **Bug behoben:** `GerichtsgutachtenView` las fälschlich `localStorage['access_token']`
  (falscher Key/Store) → jetzt über den zentralen Accessor.
- **Einziger Persistenz-Ort:** die Pinia-`auth`-Store (`stores/auth.ts`). Token in
  `sessionStorage` (nicht `localStorage`) → endet mit der Browser-Session; strenge CSP +
  XSS-Härtung (#740) reduzieren die Auslesbarkeit.
- 401-Interceptor (Logout + Redirect) und Logout/Token-Revocation (JTI-Blocklist,
  `tv`-Token-Version #738) funktionieren unverändert.

## Zielbild (Backlog / Rest-Risikoentscheidung)

Vollständige Härtung gegen Token-Diebstahl bei XSS = **kurzlebiges Access-Token nur im
Speicher + HttpOnly/SameSite-Refresh-Cookie + CSRF-Schutz**. Das ist ein größerer
Auth-Infrastruktur-Umbau (Backend: Cookie-Ausgabe + CSRF-Token + Refresh-Rotation;
flask_jwt_extended `JWT_TOKEN_LOCATION=['cookies']`), der bewusst NICHT Teil dieses
Release ist, um Login/SOC-Portal/Passkey/Demo nicht zu destabilisieren.

**Migrationspfad (ein Ort):** `auth-token.ts` ist die einzige Stelle, die dann von
„Token aus Store" auf „Cookie-basiert (kein JS-Zugriff)" umgestellt werden muss; die
Streaming-Flows nutzen dann `credentials: 'include'` statt des Authorization-Headers.
