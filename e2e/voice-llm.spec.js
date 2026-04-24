// @ts-check
// End-to-end tests for Speech-to-Text (S2T), browser Speech-to-Speech (S2S), and
// live LLM health. The Playwright config already serves `frontend/` on port 4173.
//
// The LLM-health tests require a real backend on http://127.0.0.1:8000 (use
// ./startup.sh). The S2T/S2S feature tests intercept /api/search so they can
// pass even when the LLM is down.

const { test, expect, request: pwRequest } = require("@playwright/test");

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const mockSearchResponse = {
  answer: "PM Kisan gives eligible farmers ₹6,000 per year in three installments.",
  provider: "e2e-mock",
  sources: [
    {
      scheme: "PM-KISAN",
      score: 0.88,
      apply_link: "https://pmkisan.gov.in/",
      source: "https://www.myscheme.gov.in/schemes/pm-kisan",
      confidence_label: "Strong match",
      cta_label: "Apply Now",
      preview_text: "PM Kisan Samman Nidhi",
    },
  ],
  moderation_blocked: false,
  redirect_message: null,
  moderation_category: "welfare_scheme",
  reasoning_why: null,
  near_miss_text: null,
  near_miss_sources: [],
  session_user_id: "e2e-voice-llm-session",
  confidence: "high",
  next_step: "Apply at pmkisan.gov.in with Aadhaar & land records.",
  retrieval_debug: null,
  query_debug: { original: "PM Kisan", rewritten: "PM Kisan eligibility" },
  plan: null,
  eligibility_hints: [],
};

// Injected on every page BEFORE any site JS runs.
//   - blocks the Vapi CDN so voice falls back to the browser SpeechRecognition
//   - installs a scripted SpeechRecognition implementation that we can fire
//     from the test via `window.__fakeSpeech.fire(text)`
//   - wraps window.speechSynthesis.speak so we can observe TTS calls
function getInitScript() {
  return `
    window.Vapi = undefined;
    (function () {
      const listeners = { start: [], end: [], error: [], result: [] };
      class FakeRecognition {
        constructor() {
          this.lang = "en-IN";
          this.continuous = false;
          this.interimResults = false;
          this.onstart = null;
          this.onresult = null;
          this.onend = null;
          this.onerror = null;
          window.__fakeSpeech = window.__fakeSpeech || {};
          window.__fakeSpeech.instance = this;
        }
        start() {
          window.__fakeSpeech.started = true;
          setTimeout(() => this.onstart && this.onstart({}), 0);
        }
        stop() {
          setTimeout(() => this.onend && this.onend({}), 0);
        }
        abort() { this.stop(); }
      }
      window.SpeechRecognition = FakeRecognition;
      window.webkitSpeechRecognition = FakeRecognition;
      window.__fakeSpeech = {
        fire(transcript, { isFinal = true } = {}) {
          const inst = window.__fakeSpeech.instance;
          if (!inst || !inst.onresult) return false;
          const evt = {
            resultIndex: 0,
            results: [
              Object.assign(
                [{ transcript: transcript }],
                { isFinal: isFinal }
              ),
            ],
          };
          inst.onresult(evt);
          return true;
        },
      };

      // TTS spy: capture .speak() calls so we can assert S2S triggered.
      window.__ttsCalls = [];
      if (window.speechSynthesis) {
        const origSpeak = window.speechSynthesis.speak.bind(window.speechSynthesis);
        window.speechSynthesis.speak = function (utter) {
          try {
            window.__ttsCalls.push({
              text: utter && utter.text,
              lang: utter && utter.lang,
            });
            // Fire onstart / onend so the app's state machine progresses.
            setTimeout(() => { try { utter.onstart && utter.onstart({}); } catch (_) {} }, 0);
            setTimeout(() => { try { utter.onend && utter.onend({}); } catch (_) {} }, 10);
          } catch (_) {}
          try { return origSpeak(utter); } catch (_) { return undefined; }
        };
      } else {
        // Minimal stub if the browser doesn't expose speechSynthesis.
        const cancel = () => {};
        const speak = (utter) => {
          window.__ttsCalls.push({ text: utter && utter.text, lang: utter && utter.lang });
          setTimeout(() => { try { utter.onstart && utter.onstart({}); } catch (_) {} }, 0);
          setTimeout(() => { try { utter.onend && utter.onend({}); } catch (_) {} }, 10);
        };
        window.speechSynthesis = { speak, cancel, getVoices: () => [], onvoiceschanged: null };
        window.SpeechSynthesisUtterance = function (text) {
          this.text = text; this.lang = ""; this.voice = null;
          this.onstart = null; this.onend = null; this.onerror = null;
        };
      }
    })();
  `;
}

test.beforeEach(async ({ page, context }) => {
  await context.addInitScript(getInitScript());
  // Block the Vapi CDN so the browser-SpeechRecognition fallback path is used.
  await page.route(/vapi/i, (route) => route.abort());
});

// ---------- LLM / backend health (needs real backend) ------------------------

test("backend /health reports online", async () => {
  const api = await pwRequest.newContext();
  const res = await api.get(`${BACKEND_URL}/health`, { timeout: 10_000 });
  expect(res.ok()).toBe(true);
  const json = await res.json();
  expect(json.status).toBe("online");
  expect(typeof json.model).toBe("string");
  await api.dispose();
});

test("live LLM returns a real provider answer (not fallback 'unavailable')", async () => {
  const api = await pwRequest.newContext();
  const res = await api.post(`${BACKEND_URL}/api/search`, {
    data: {
      query: "What is PM Kisan and who is eligible?",
      language: "en-IN",
      include_plan: false,
    },
    timeout: 60_000,
  });
  expect(res.ok()).toBe(true);
  const json = await res.json();
  expect(json).toHaveProperty("answer");
  expect(json).toHaveProperty("provider");
  expect(Array.isArray(json.sources)).toBe(true);
  expect(json.sources.length).toBeGreaterThan(0);
  // If the LLM pipeline is healthy, provider is "gemini-..." or "groq-...".
  // If both keys are invalid/expired, the backend returns provider "unavailable"
  // with a canned apology — surface that as a real failure here.
  expect(
    json.provider,
    `Got fallback provider "${json.provider}" — both Gemini and Groq likely failed. Answer was: ${json.answer}`
  ).not.toBe("unavailable");
  await api.dispose();
});

// ---------- S2T: browser Speech Recognition -> /api/search -------------------

test("S2T: voice button fires browser SpeechRecognition and sends query", async ({ page }) => {
  // Intercept the search call so we can assert it was invoked with the
  // transcribed text, independent of LLM health.
  let capturedRequestBody = null;
  await page.route("**/api/search", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    capturedRequestBody = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json", "X-Trace-Id": "e2e-s2t" },
      body: JSON.stringify(mockSearchResponse),
    });
  });

  await page.goto("/");
  // Click the voice button — since Vapi CDN is blocked, the app must use the
  // browser SpeechRecognition fallback (which is our FakeRecognition).
  await page.locator("#voiceBtn").click();

  // Wait for start callback to flip UI into listening state.
  await expect(page.locator("#voiceBtn")).toHaveClass(/active/, { timeout: 5_000 });

  // Simulate the user finishing speaking: fire a final transcript.
  const fired = await page.evaluate(() => window.__fakeSpeech.fire("PM Kisan eligibility"));
  expect(fired).toBe(true);

  // The user's transcribed message should appear in the conversation.
  await expect(page.locator("#conversation .message.user")).toContainText(
    "PM Kisan eligibility",
    { timeout: 10_000 }
  );

  // And /api/search must have been called with that query.
  await expect.poll(() => capturedRequestBody?.query, { timeout: 10_000 }).toBe(
    "PM Kisan eligibility"
  );
  expect(capturedRequestBody).toMatchObject({
    query: "PM Kisan eligibility",
    language: expect.any(String),
  });

  // Mock response rendered as assistant message.
  await expect(page.locator("#conversation .message.assistant")).toContainText(
    "PM Kisan gives eligible farmers",
    { timeout: 10_000 }
  );
});

// ---------- S2S: browser SpeechSynthesis after assistant reply --------------

test("S2S: assistant answer is spoken via SpeechSynthesis", async ({ page }) => {
  await page.route("**/api/search", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json", "X-Trace-Id": "e2e-s2s" },
      body: JSON.stringify(mockSearchResponse),
    });
  });

  await page.goto("/");
  await page.locator("#textInput").fill("PM Kisan");
  await page.locator("#sendBtn").click();

  await expect(page.locator("#conversation .message.assistant")).toContainText(
    "PM Kisan gives eligible farmers",
    { timeout: 15_000 }
  );

  // speechSynthesis.speak must have been called with the answer text.
  await expect
    .poll(() => page.evaluate(() => window.__ttsCalls.length), { timeout: 10_000 })
    .toBeGreaterThan(0);

  const calls = await page.evaluate(() => window.__ttsCalls);
  expect(calls[0].text).toContain("PM Kisan gives eligible farmers");
});

// ---------- Full S2T -> /api/search -> S2S round trip ------------------------

test("S2T + S2S round-trip: speech in, spoken answer out", async ({ page }) => {
  await page.route("**/api/search", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json", "X-Trace-Id": "e2e-roundtrip" },
      body: JSON.stringify(mockSearchResponse),
    });
  });

  await page.goto("/");
  await page.locator("#voiceBtn").click();
  await expect(page.locator("#voiceBtn")).toHaveClass(/active/, { timeout: 5_000 });
  await page.evaluate(() => window.__fakeSpeech.fire("housing scheme for BPL"));

  await expect(page.locator("#conversation .message.user")).toContainText(
    "housing scheme for BPL"
  );
  await expect(page.locator("#conversation .message.assistant")).toContainText(
    "PM Kisan gives eligible farmers"
  );
  await expect
    .poll(() => page.evaluate(() => window.__ttsCalls.length), { timeout: 10_000 })
    .toBeGreaterThan(0);
});

// ---------- Moderation block is rendered without LLM -------------------------

test("moderation block is rendered when backend returns moderation_blocked", async ({ page }) => {
  await page.route("**/api/search", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...mockSearchResponse,
        answer: "",
        moderation_blocked: true,
        moderation_category: "off_topic",
        redirect_message: "I help with government schemes and civic services.",
      }),
    });
  });

  await page.goto("/");
  await page.locator("#textInput").fill("tell me a joke");
  await page.locator("#sendBtn").click();
  await expect(page.locator("#conversation .moderation-block")).toContainText(
    "I help with government schemes and civic services.",
    { timeout: 10_000 }
  );
});

// ---------- Language + Finder / Eligibility wiring --------------------------

test("language pill switches and finder form posts eligibility query", async ({ page }) => {
  let capturedQuery = null;
  await page.route("**/api/search", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    capturedQuery = route.request().postDataJSON()?.query;
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mockSearchResponse),
    });
  });

  await page.goto("/");
  await page.locator('[data-action="toggle-lang"]').click();
  await page.locator('[data-action="select-language"][data-lang="en-IN"]').click();
  await expect(page.locator('[data-action="select-language"][data-lang="en-IN"]')).toHaveClass(
    /active/
  );

  await page.locator('[data-action="mode-finder"]').click();
  await expect(page.locator("#finderPanel")).not.toHaveClass(/hidden/);
  await page.locator("#finderState").selectOption("Karnataka");
  await page.locator('input[name="finderRole"][value="farmer"]').check();
  await page.locator('input[name="finderIncome"][value="below 1 lakh"]').check();
  await page.locator('.finder-submit').click();

  await expect
    .poll(() => capturedQuery, { timeout: 10_000 })
    .toMatch(/farmer.*Karnataka/i);
});
