# Dashboard Home Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a unified dashboard aggregation API and migrate the frontend shell to a top-navigation portal homepage without breaking existing data pages.

**Architecture:** The backend adds a read-only dashboard service and a dedicated API endpoint that aggregates homepage summary, species cards, distributions, and map data from `Species`, `Accession`, `Sample`, `Dataset`, `DataFile`, and `FileRelation`. The frontend adds a new `DashboardHomeView` with focused presentational components that consume only the dashboard API, while `App.vue` and router are updated to expose the dashboard as the default entry and preserve existing feature routes.

**Tech Stack:** Django, Django REST Framework function views, Vue 3, Vue Router 4, Element Plus, ECharts, Axios

---

### Task 1: Lock Dashboard API Behavior With Tests

**Files:**
- Create: `django2/files/tests/test_dashboard_api.py`
- Modify: `django2/filemanager/urls.py`
- Modify: `django2/files/models.py` (read only for reference, no code changes)

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run `python manage.py test files.tests.test_dashboard_api --keepdb -v 2` and verify it fails**
- [ ] **Step 3: Add the minimal dashboard endpoint wiring and service implementation**
- [ ] **Step 4: Re-run `python manage.py test files.tests.test_dashboard_api --keepdb -v 2` and verify it passes**

### Task 2: Add Read-Only Dashboard Aggregation Service

**Files:**
- Create: `django2/files/services/dashboard_service.py`
- Create: `django2/files/dashboard_views.py`
- Modify: `django2/filemanager/urls.py`

- [ ] **Step 1: Implement summary aggregation**
- [ ] **Step 2: Implement species card aggregation**
- [ ] **Step 3: Implement dataset type / file role distributions**
- [ ] **Step 4: Implement geographic aggregation**
- [ ] **Step 5: Expose `GET /gd/api/warehouse/dashboard/`**

### Task 3: Add Dashboard Frontend Data Layer and Components

**Files:**
- Create: `vue_project/src/services/dashboard.js`
- Create: `vue_project/src/config/dashboardSearch.js`
- Create: `vue_project/src/components/TopNavBar.vue`
- Create: `vue_project/src/components/DashboardHero.vue`
- Create: `vue_project/src/components/SpeciesCardGrid.vue`
- Create: `vue_project/src/components/DistributionPanel.vue`
- Create: `vue_project/src/components/GeoMapPanel.vue`
- Create: `vue_project/src/views/DashboardHomeView.vue`

- [ ] **Step 1: Add dashboard API client**
- [ ] **Step 2: Add structured search routing config**
- [ ] **Step 3: Build top navigation component**
- [ ] **Step 4: Build homepage presentational components**
- [ ] **Step 5: Build dashboard view using only unified dashboard data**

### Task 4: Switch Application Shell to Top Navigation

**Files:**
- Modify: `vue_project/src/App.vue`
- Modify: `vue_project/src/router/index.js`
- Modify: `vue_project/src/views/LoginView.vue`
- Modify: `vue_project/src/i18n/index.js`

- [ ] **Step 1: Replace sidebar shell with top-navigation shell**
- [ ] **Step 2: Add `/` and `/dashboard` routes**
- [ ] **Step 3: Redirect post-login flow to `/dashboard`**
- [ ] **Step 4: Keep old business routes reachable**
- [ ] **Step 5: Add dashboard-related i18n labels**

### Task 5: Verify End-to-End Safety

**Files:**
- Modify: `django2/files/tests/test_dashboard_api.py` (only if coverage gaps remain)

- [ ] **Step 1: Run backend tests**
- [ ] **Step 2: Run `python manage.py check`**
- [ ] **Step 3: Run `python manage.py makemigrations files --check --dry-run`**
- [ ] **Step 4: Run `npm run build` in `vue_project`**
- [ ] **Step 5: Review that no `/genome-files/` download link is introduced on the dashboard**
