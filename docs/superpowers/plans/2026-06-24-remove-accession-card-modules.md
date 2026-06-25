# Remove Accession Card Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the `Current Modules` and `Assemblies` panels from the accession card without affecting accession overview data, summary counts, routes, or independent module pages.

**Architecture:** Keep the accession detail request and assembly/annotation data because the overview summary still uses them. Remove only the two rendered panels and the script/CSS code exclusively responsible for resource cards, hierarchy interactions, and SVG connector layout.

**Tech Stack:** Vue 3, Element Plus, Node.js built-in test runner.

---

### Task 1: Lock the desired page structure

**Files:**
- Create: `vue_project/tests/accession-card-module-cleanup.test.mjs`
- Test: `vue_project/tests/accession-card-module-cleanup.test.mjs`

- [ ] Add a static regression test that reads `AccessionCard.vue`.
- [ ] Assert that the accession overview remains.
- [ ] Assert that `Current Modules`, the `Assemblies` panel, resource cards, and hierarchy graph markup are absent.
- [ ] Run the test and confirm it fails before implementation.

### Task 2: Remove module and hierarchy implementation

**Files:**
- Modify: `vue_project/src/views/AccessionCard.vue`

- [ ] Remove both panel template blocks and the already-disabled context block.
- [ ] Remove resource-card generation and navigation/download helpers used only by those panels.
- [ ] Remove hierarchy refs, connector calculations, selection handlers, resize listeners, and return exports used only by the hierarchy panel.
- [ ] Keep assembly/annotation loading and summary tooltip data intact.

### Task 3: Remove dead presentation styles and verify

**Files:**
- Modify: `vue_project/src/views/AccessionCard.vue`
- Test: `vue_project/tests/accession-card-module-cleanup.test.mjs`

- [ ] Remove CSS selectors dedicated to resource cards, hierarchy nodes, connectors, and the removed grid sections.
- [ ] Run the focused regression test.
- [ ] Run all frontend static tests.
- [ ] Run the production frontend build.

