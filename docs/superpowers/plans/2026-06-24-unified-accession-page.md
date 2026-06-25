# Unified Accession Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one Accession page for both compatibility routes using authoritative new-structure data and the existing Accession Structure graph.

**Architecture:** Extend the current accession detail endpoint with hierarchy-wide DataFile/FileRelation inventory and summary metadata. Rebuild `AccessionDetailTableView.vue` around the approved two-column layout, retain its structure graph logic, and point both frontend routes to that component without redirects.

**Tech Stack:** Django REST Framework, Django ORM, Vue 3, Vue Router, Element Plus, Node test runner.

---

### Task 1: Define backend aggregation contract

**Files:**
- Modify: `django2/files/tests/test_accession_detail_file_relation_integration.py`
- Modify: `django2/files/views.py`

- [ ] Add a test creating Species, Sample, Project, Dataset, hierarchy relations and duplicate DataFile relations.
- [ ] Assert hierarchy-wide files are returned once and summary counts/sizes are correct.
- [ ] Run the focused Django test and confirm failure before implementation.
- [ ] Implement the aggregation using FileRelation and DataFile only.
- [ ] Run the focused Django test and confirm success.

### Task 2: Define unified frontend contract

**Files:**
- Create: `vue_project/tests/unified-accession-page.test.mjs`
- Modify: `vue_project/src/router/index.js`
- Modify: `vue_project/src/views/AccessionDetailTableView.vue`

- [ ] Add static tests asserting both routes import the same component.
- [ ] Assert the page contains Accession title, description, summary cards, 组装版本, annotation, related files, relationship overview, status and timestamps.
- [ ] Assert no back-to-list control is present.
- [ ] Run the focused test and confirm failure.
- [ ] Point both routes to the unified component and implement the approved layout.
- [ ] Run the focused test and confirm success.

### Task 3: Regression verification

**Files:**
- Test: `django2/files/tests/test_accession_detail_file_relation_integration.py`
- Test: `vue_project/tests/unified-accession-page.test.mjs`

- [ ] Run accession backend integration tests.
- [ ] Run all frontend static tests.
- [ ] Run `python manage.py check`.
- [ ] Run `python manage.py makemigrations files --check --dry-run`.
- [ ] Run `npm run build`.

