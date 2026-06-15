<template>
  <div class="admin-dashboard">
    <div class="header">
      <h2>🛡️ Administration</h2>
      <p>Systemverwaltung, Audit, Datenbank und Konfiguration</p>
    </div>

    <div class="card-grid">
      <router-link
        v-for="card in cards"
        :key="card.path"
        :to="card.path"
        class="admin-card"
      >
        <div class="card-icon">{{ card.icon }}</div>
        <h3>{{ card.title }}</h3>
        <p>{{ card.description }}</p>
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
const cards = [
  {
    path: '/admin/settings',
    icon: '⚙️',
    title: 'Einstellungen',
    description: 'KI-Provider, GitHub, Module, Backup, Aussehen — alles an einem Ort',
  },
  {
    path: '/admin/users',
    icon: '👥',
    title: 'Benutzerverwaltung',
    description: 'Konten anlegen, Rollen ändern, Passwörter zurücksetzen',
  },
  {
    path: '/admin/frameworks',
    icon: '📚',
    title: 'Framework-Bibliothek',
    description: 'Regulierungs-PDFs (DORA, NIS2, CRA, DSGVO, AI Act, BSI) herunterladen + ingestieren',
  },
  {
    path: '/admin/wiba-catalog',
    icon: '🛡️',
    title: 'WiBA-Katalog',
    description: 'BSI „Weg in die Basis-Absicherung" — Checklisten/Prüffragen herunterladen + importieren',
  },
  {
    path: '/admin/firmen-link',
    icon: '🔗',
    title: 'Firmen-Zuordnung',
    description: 'Projekte ihren Firmen zuordnen (firmen_id) — Voraussetzung fürs Risiko-Cockpit (#1071)',
  },
  {
    path: '/admin/audit',
    icon: '📜',
    title: 'Audit-Log',
    description: 'Alle HTTP-Requests, Logins und Aktionen mit Zeitstempel',
  },
  {
    path: '/admin/db',
    icon: '🗄️',
    title: 'DB-Viewer',
    description: 'SQLite-Datenbanken einsehen, Tabellen explorieren',
  },
  {
    path: '/admin/backup',
    icon: '💾',
    title: 'Backup-Verwaltung',
    description: 'DB-Snapshots erstellen, herunterladen, wiederherstellen',
  },
  {
    path: '/admin/issues',
    icon: '🐛',
    title: 'Issue-Übersicht',
    description: 'GitHub-/GitLab-Issues über alle Module hinweg verwalten',
  },
  {
    path: '/admin/ollama',
    icon: '🧠',
    title: 'KI-Modelle (Ollama)',
    description: 'Installierte Modelle anzeigen, neue Modelle pullen, alte löschen',
  },
  {
    path: '/admin/license',
    icon: '🔑',
    title: 'Lizenz',
    description: 'Aktivierung, Status, Module + Read-Only-Banner',
  },
  {
    path: '/admin/templates',
    icon: '📄',
    title: 'Word-Vorlagen',
    description: 'Zentrale Vorlagen-Verwaltung für CRA, NIS2, AI Act, DSGVO, Risikobewertung',
  },
]
</script>

<style scoped>
.admin-dashboard { max-width: 1200px; padding: 16px; }

.header { margin-bottom: 24px; padding-bottom: 12px; border-bottom: 1px solid var(--color-border); }
.header h2 { margin: 0; font-size: 22px; }
.header p { margin: 2px 0 0; color: var(--color-text-secondary); font-size: 13px; }

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.admin-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 24px;
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: transform 150ms, box-shadow 150ms, border-color 150ms;
}
.admin-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.1);
  border-color: var(--color-primary);
}
.card-icon { font-size: 32px; }
.admin-card h3 { margin: 0; font-size: 16px; color: var(--color-primary); }
.admin-card p { margin: 0; color: var(--color-text-secondary); font-size: 13px; line-height: 1.4; }
</style>
