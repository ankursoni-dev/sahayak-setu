// @ts-check
const { test, expect } = require('@playwright/test');

const mockSearchResponse = {
  answer: 'E2E mock: PM Kisan summary for testing.',
  provider: 'e2e-mock',
  sources: [],
  moderation_blocked: false,
  redirect_message: null,
  moderation_category: null,
  reasoning_why: null,
  near_miss_text: null,
  near_miss_sources: [],
  session_user_id: 'e2e-session-user',
  confidence: 'high',
  next_step: null,
  retrieval_debug: null,
  query_debug: { original: 'PM Kisan', rewritten: 'PM Kisan' },
  plan: null,
  eligibility_hints: [],
};

test.beforeEach(async ({ page }) => {
  await page.route('**/api/search', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'X-Trace-Id': 'e2e-trace-1',
      },
      body: JSON.stringify(mockSearchResponse),
    });
  });
  await page.route('**/api/feedback', (route) => route.fulfill({ status: 200, body: '{}' }));
  await page.route('**/api/error', (route) => route.fulfill({ status: 200, body: '{}' }));
});

test('home page loads with branding', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/SahayakSetu/);
  await expect(page.getByRole('banner').getByText('sahayaksetu')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toContainText(/Every voice/i);
});

test('text send shows mocked assistant answer', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('searchbox').first().fill('PM Kisan eligibility');
  await page.getByRole('button', { name: /send/i }).click();
  await expect(page.getByRole('log', { name: /conversation/i })).toContainText('E2E mock:', { timeout: 20_000 });
});

test('finder mode toggle shows finder panel', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('tab', { name: /find schemes/i }).click();
  await expect(page.getByRole('heading', { name: /eligibility finder/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /search schemes/i })).toBeVisible();
});

test('language switcher opens and selects English', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /change language/i }).click();
  await page.getByRole('option', { name: /English/i }).click();
  await expect(page.getByRole('button', { name: /change language/i })).toContainText('English');
});

test('curated scheme card opens detail sheet', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /view details for PM Kisan/i }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole('heading', { name: /PM Kisan/i })).toBeVisible();
  await dialog.getByRole('button', { name: /close/i }).click();
  await expect(dialog).toBeHidden();
});

test("voice toggle doesn't leave status stuck on Listening", async ({ page }) => {
  await page.goto('/');
  const banner = page.getByRole('banner');
  // Sanity: initial status pill reads Ready.
  await expect(banner.getByText(/Ready/i)).toBeVisible();
  // Tap the voice button. Under automation (navigator.webdriver) Vapi is skipped and
  // we fall straight to browser SpeechRecognition — which in headless Chromium errors
  // out immediately and our finish() handler should reset the status pill to Ready.
  await page.getByRole('button', { name: /start voice/i }).click();
  await page.waitForTimeout(3000);
  const headerText = (await banner.textContent()) ?? '';
  expect(headerText).not.toMatch(/Listening\.\.\./);
  // And it should have settled to Ready or Voice unavailable.
  expect(headerText).toMatch(/Ready|Voice unavailable/);
});

test('real backend returns 200 with sources', async ({ page }) => {
  // Unroute the global mock so this test hits the live backend.
  await page.unroute('**/api/search');
  await page.goto('/');
  const searchResponse = page.waitForResponse(
    (r) => r.url().includes('/api/search') && r.request().method() === 'POST',
    { timeout: 60_000 },
  );
  await page.getByRole('searchbox').first().fill('PM Kisan eligibility');
  await page.getByRole('button', { name: /send/i }).click();
  const resp = await searchResponse;
  expect(resp.status(), `backend returned ${resp.status()}`).toBe(200);
  const body = await resp.json();
  expect(body.moderation_blocked).toBe(false);
  expect(Array.isArray(body.sources)).toBe(true);
  expect(body.sources.length).toBeGreaterThan(0);
});
