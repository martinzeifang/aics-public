<template>
  <div class="admin-dashboard">
    <div class="header">
      <h2>{{ $t('admin.adminDashboardView.administration') }}</h2>
      <p>{{ $t('admin.adminDashboardView.systemverwaltungAuditDatenbankUndKon') }}</p>
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
import { t } from '../../i18n'

const cards = [
  {
    path: '/admin/settings',
    icon: '⚙️',
    title: t('app.settings'),
    description: t('admin.adminDashboardView.kIProviderGitHubModuleBackupAussehen'),
  },
  {
    path: '/admin/users',
    icon: '👥',
    title: t('admin.adminDashboardView.benutzerverwaltung'),
    description: t('admin.adminDashboardView.kontenAnlegenRollenAndernPassworterZ'),
  },
  {
    path: '/admin/groups',
    icon: '👪',
    title: t('admin.adminDashboardView.gruppen'),
    description: t('admin.adminDashboardView.berechtigungenEinmalVergebenUndBenut'),
  },
  {
    path: '/admin/frameworks',
    icon: '📚',
    title: t('admin.adminDashboardView.frameworkBibliothek'),
    description: 'Regulierungs-PDFs (NIS2, CRA, DSGVO, AI Act, BSI) herunterladen + ingestieren',
  },
  {
    path: '/admin/wiba-catalog',
    icon: '🛡️',
    title: t('admin.adminDashboardView.wiBAKatalog'),
    description: t('admin.adminDashboardView.bSIWegInDieBasisAbsicherungChecklist'),
  },
  {
    path: '/admin/licensing',
    icon: '🧾',
    title: t('admin.adminDashboardView.mandantenAbrechnung'),
    description: t('admin.adminDashboardView.abrechnungsgrundlageJeMandantPreisbl'),
  },
  {
    path: '/admin/firmen-link',
    icon: '🔗',
    title: t('admin.adminDashboardView.firmenZuordnung'),
    description: t('admin.adminDashboardView.projekteIhrenFirmenZuordnenFirmenIdV'),
  },
  {
    path: '/admin/audit',
    icon: '📜',
    title: t('admin.adminDashboardView.auditLog'),
    description: t('admin.adminDashboardView.alleHTTPRequestsLoginsUndAktionenMit'),
  },
  {
    path: '/admin/db',
    icon: '🗄️',
    title: t('admin.adminDashboardView.dBViewer'),
    description: t('admin.adminDashboardView.sQLiteDatenbankenEinsehenTabellenExp'),
  },
  {
    path: '/admin/backup',
    icon: '💾',
    title: t('admin.adminDashboardView.backupVerwaltung'),
    description: t('admin.adminDashboardView.dBSnapshotsErstellenHerunterladenWie'),
  },
  {
    path: '/admin/issues',
    icon: '🐛',
    title: t('admin.adminDashboardView.issueUbersicht'),
    description: t('admin.adminDashboardView.gitHubGitLabIssuesUberAlleModuleHinw'),
  },
  {
    path: '/admin/ollama',
    icon: '🧠',
    title: t('admin.adminDashboardView.kIModelleOllama'),
    description: t('admin.adminDashboardView.installierteModelleAnzeigenNeueModel'),
  },
  {
    path: '/admin/license',
    icon: '🔑',
    title: t('license.title'),
    description: t('admin.adminDashboardView.aktivierungStatusModuleReadOnlyBanne'),
  },
  {
    path: '/admin/templates',
    icon: '📄',
    title: t('admin.adminDashboardView.wordVorlagen'),
    description: t('admin.adminDashboardView.zentraleVorlagenVerwaltungFurCRANIS2'),
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
