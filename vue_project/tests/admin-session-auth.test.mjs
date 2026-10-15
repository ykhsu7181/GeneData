import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const currentDir = path.dirname(fileURLToPath(import.meta.url));
const readSource = (relativePath) => fs.readFileSync(path.resolve(currentDir, relativePath), 'utf8');

const mainSource = readSource('../src/main.js');
const loginSource = readSource('../src/views/AdminLogin.vue');
const dashboardSource = readSource('../src/views/AdminDashboard.vue');
const routerSource = readSource('../src/router/index.js');

test('axios sends Django session cookies and CSRF headers', () => {
  assert.match(mainSource, /axios\.defaults\.withCredentials\s*=\s*true/);
  assert.match(mainSource, /xsrfCookieName\s*=\s*'csrftoken'/);
  assert.match(mainSource, /xsrfHeaderName\s*=\s*'X-CSRFToken'/);
});

test('admin UI uses server-side session state instead of localStorage tokens', () => {
  assert.match(loginSource, /axios\.get\('\/admin\/session\/'\)/);
  assert.match(loginSource, /axios\.post\('\/admin\/login\/'/);
  assert.match(dashboardSource, /axios\.post\('\/admin\/logout\/'\)/);
  assert.match(routerSource, /response\.data\.user\?\.is_staff\s*===\s*true/);

  for (const source of [loginSource, dashboardSource, routerSource]) {
    assert.doesNotMatch(source, /admin_token|admin_user|isLoggedIn/);
  }
});

test('public routes bypass the retired client-side login while admin stays protected', () => {
  assert.match(routerSource, /path:\s*'\/login',[\s\S]*?redirect:\s*'\/dashboard'/);
  assert.doesNotMatch(routerSource, /views\/LoginView\.vue/);
  assert.doesNotMatch(routerSource, /localStorage\.getItem\('isLoggedIn'\)/);
  assert.match(routerSource, /path:\s*'\/dashboard'[\s\S]*?requiresAuth:\s*false/);
  assert.match(routerSource, /path:\s*'\/admin\/dashboard'[\s\S]*?requiresAdminAuth:\s*true/);
  assert.doesNotMatch(loginSource, /defaultAccount|root123/);
});

