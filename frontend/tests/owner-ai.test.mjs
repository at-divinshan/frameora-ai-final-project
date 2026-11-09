import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { build } from "esbuild";

const root = process.cwd();
const temporary = await mkdtemp(path.join(root, "tests/.owner-ai-"));

try {
  const serviceFile = path.join(temporary, "service.mjs");
  await build({
    stdin: {
      contents: 'export * from "./src/services/ownerAiService.js"; export {default as api} from "./src/services/api.js";',
      resolveDir: root,
    },
    bundle: true,
    format: "esm",
    platform: "node",
    packages: "external",
    outfile: serviceFile,
    define: { "import.meta.env": JSON.stringify({ VITE_API_URL: "http://localhost:8000" }) },
  });
  const uiFile = path.join(temporary, "ui.mjs");
  await build({
    stdin: {
      contents: 'export * from "./src/config/ownerPreferences"; export {default as OwnerCustomization} from "./src/components/ai/OwnerCustomization"; export {OwnerEntitlementSummary, OwnerGenerationImages, OwnerGenerationConfirmation, linkedProjectIsEditable} from "./src/pages/owner/AIGenerator.jsx"; export {PlanCards} from "./src/pages/owner/Subscription.jsx"; export {OWNER_GENERATION_CONTRACT, isOwnerGalleryBatch, ownerGenerationAllowed} from "./src/config/ownerGeneration.js";',
      resolveDir: root,
    },
    bundle: true,
    format: "esm",
    platform: "node",
    packages: "external",
    outfile: uiFile,
    jsx: "automatic",
    loader: { ".css": "empty" },
    define: { "import.meta.env": JSON.stringify({ VITE_API_URL: "http://localhost:8000" }) },
  });

  const service = await import(pathToFileURL(serviceFile));
  const ui = await import(pathToFileURL(uiFile));
  assert.deepEqual(ui.OWNER_GENERATION_CONTRACT, {
    batchSize: 2,
    batchCost: 2,
    requestTimeoutMs: 1300000,
  });
  const React = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { MemoryRouter } = await import("react-router-dom");
  const requests = [];
  service.api.defaults.adapter = async (config) => {
    requests.push(config);
    return { data: { id: 21, status: "completed", images: [] }, status: 200, headers: {}, config };
  };

  test("testing mode displays two images and two credits while historical galleries remain supported", () => {
    const html = renderToStaticMarkup(React.createElement(ui.OwnerGenerationConfirmation, {
      entitlement: { remaining_credits: 10, batch_cost: 2, generation_allowed: true }, busy: false,
    }));
    assert.ok(html.includes("This batch generates 2 images and reserves 2 credits"));
    assert.ok(html.includes("Confirm and generate (2 credits)"));
    for (const count of [2, 4, 8]) {
      assert.equal(ui.isOwnerGalleryBatch(Array(count), ui.OWNER_GENERATION_CONTRACT, count), true);
      assert.equal(ui.isOwnerGalleryBatch(Array(count), { batchSize: 8, batchCost: 8 }, count), true);
    }
  });

  test("owner-only services use the verified endpoints and backend request fields", async () => {
    const entitlement = { plan: "basic", remaining_credits: 10 };
    const plans = [{ id: 3, photography_type: "Portrait" }];
    service.api.defaults.adapter = async (config) => {
      requests.push(config);
      return { data: config.url === "/owner/entitlements" ? entitlement : plans, status: 200, headers: {}, config };
    };
    assert.deepEqual(await service.getOwnerEntitlements(), entitlement);
    assert.deepEqual(await service.getOwnerPhotographyPlans(), plans);
    assert.equal(requests[0].url, "/owner/entitlements");
    assert.equal(requests[1].url, "/owner/photography-plans");

    requests.length = 0;
    await service.generateOwnerImages({
      planId: 3,
      description: "Studio portrait",
      reference: new Blob(["fixture"], { type: "image/png" }),
      idempotencyKey: "stable-key-for-retry-001",
    });
    const request = requests[0];
    assert.equal(request.url, "/owner/ai/generations");
    assert.equal(request.data.get("plan_id"), "3");
    assert.equal(request.data.get("description"), "Studio portrait");
    assert.equal(request.data.get("idempotency_key"), "stable-key-for-retry-001");
    assert.equal(request.data.get("reference").type, "image/png");
    assert.equal(request.timeout, 1300000);
    assert.notEqual(request.headers["Content-Type"], "application/json");

    requests.length = 0;
    await service.generateOwnerImages({
      planId: 10,
      projectId: 7,
      idempotencyKey: "project-plan-key-000001",
    });
    assert.equal(requests[0].url, "/owner/projects/7/ai/generations");
    assert.equal(requests[0].data.get("plan_id"), "10");
    assert.equal(requests[0].data.get("description"), "");
    assert.equal(requests[0].data.has("reference"), false);
  });

  test("retries preserve a caller-supplied key and gallery calls stay owner-scoped", async () => {
    requests.length = 0;
    service.api.defaults.adapter = async (config) => {
      requests.push(config);
      return { data: [{ id: 8, status: "owner_reserved" }], status: 200, headers: {}, config };
    };
    const body = { planId: 3, description: "Same batch", idempotencyKey: "stable-key-for-retry-002" };
    await service.generateOwnerImages(body);
    await service.generateOwnerImages(body);
    await service.getOwnerGenerations();
    await service.getOwnerGeneration(8);
    await service.recoverOwnerGeneration(8);
    await service.getOwnerGeneratedImage(11);
    assert.equal(requests[0].data.get("idempotency_key"), requests[1].data.get("idempotency_key"));
    assert.deepEqual(requests.slice(2).map(({ method, url }) => [method, url]), [
      ["get", "/owner/ai/generations"],
      ["get", "/owner/ai/generations/8"],
      ["post", "/owner/ai/generations/8/recover"],
      ["get", "/owner/ai/images/11"],
    ]);
    assert.equal(requests[5].responseType, "blob");
  });

  test("backend HTTP statuses map to friendly owner generation messages", () => {
    assert.match(service.ownerGenerationError({ response: { status: 402 } }), /not enough available credits/i);
    assert.match(service.ownerGenerationError({ response: { status: 401 } }), /session has expired/i);
    assert.match(service.ownerGenerationError({ response: { status: 403 } }), /do not have access/i);
    assert.match(service.ownerGenerationError({ response: { status: 409, data: { detail: { generation_id: 9 } } } }), /already in progress/i);
    assert.match(service.ownerGenerationError({ response: { status: 503, data: { detail: { generation_id: 9 } } } }), /status is uncertain/i);
    assert.match(service.ownerGenerationError({ response: { status: 503 } }), /temporarily unavailable/i);
    assert.match(service.ownerGenerationError({ response: { status: 422 } }), /reference photo/i);
    assert.match(service.ownerGenerationStatusMessage({ status: "owner_reserved" }), /do not start another generation/i);
    assert.match(service.ownerGenerationStatusMessage({ status: "failed" }), /credits were refunded/i);
  });

  test("customization uses supported values and requires instructions for custom selections", () => {
    const defaults = { ...ui.DEFAULT_OWNER_PREFERENCES };
    assert.deepEqual(ui.validateOwnerPreferences(defaults), {});
    for (const mode of ['background_mode', 'pose_mode', 'camera_angle_mode']) {
      assert.ok(ui.validateOwnerPreferences({ ...defaults, [mode]: 'custom', additional_instructions: '  ' }).additional_instructions);
      assert.deepEqual(ui.validateOwnerPreferences({ ...defaults, [mode]: 'custom', additional_instructions: 'Use a garden, seated poses and low angles.' }), {});
    }
    assert.ok(ui.validateOwnerPreferences({ ...defaults, outfit_mode: 'custom' }).outfit_details);
    assert.deepEqual(ui.validateOwnerPreferences({ ...defaults, outfit_mode: 'custom', outfit_details: 'Blue formal suit' }), {});
    for (const [key, , options] of ui.OWNER_PREFERENCE_MODES) {
      assert.ok(ui.validateOwnerPreferences({ ...defaults, [key]: 'unsupported' })[key]);
      for (const value of options) assert.deepEqual(ui.validateOwnerPreferences({ ...defaults, [key]: value, outfit_details: 'Suit', additional_instructions: 'Custom scene' }), {});
    }
    for (const [key, , limit] of ui.OWNER_PREFERENCE_TEXT) {
      assert.ok(ui.validateOwnerPreferences({ ...defaults, [key]: 'x'.repeat(limit + 1) })[key]);
      assert.deepEqual(ui.validateOwnerPreferences({ ...defaults, [key]: 'x'.repeat(limit) }), {});
    }
    const html = renderToStaticMarkup(React.createElement(ui.OwnerCustomization, {
      values: { ...defaults, outfit_mode: 'custom', background_mode: 'custom' }, disabled: true,
      errors: { outfit_details: 'Add Outfit Details' },
    }));
    for (const [key, label] of [...ui.OWNER_PREFERENCE_MODES, ...ui.OWNER_PREFERENCE_TEXT]) {
      assert.ok(html.includes(`name="${key}"`)); assert.ok(html.includes(label));
    }
    assert.match(html, /fieldset disabled/);
    assert.match(html, /required for custom selections/);
    assert.match(html, /aria-invalid="true"/);
  });

  test("customization multipart fields and retries match for studio and project generation", async () => {
    requests.length = 0;
    service.api.defaults.adapter = async config => { requests.push(config); return { data: {}, status: 200, config, headers: {} }; };
    const preferences = { background_mode: 'different', pose_mode: 'high', camera_angle_mode: 'cinematic', outfit_mode: 'custom', dress_colors: 'Blue, gold', outfit_details: 'Formal suit', additional_instructions: 'Garden at sunset' };
    for (const projectId of [undefined, 7]) {
      const body = { planId: 3, projectId, preferences, idempotencyKey: 'stable-custom-key-0001' };
      await service.generateOwnerImages(body);
      await service.generateOwnerImages(JSON.parse(JSON.stringify(body)));
      const [first, retry] = requests.slice(-2);
      assert.equal(first.url, projectId ? '/owner/projects/7/ai/generations' : '/owner/ai/generations');
      assert.deepEqual([...first.data.entries()], [...retry.data.entries()]);
      for (const [key, value] of Object.entries(preferences)) assert.deepEqual(first.data.getAll(key), [value]);
      assert.equal(first.data.has('preferences'), false);
      assert.equal(first.data.has('prompt'), false);
    }
    const before = requests.length;
    await assert.rejects(service.generateOwnerImages({ planId: 3, preferences: { ...preferences, outfit_details: '' } }), /Invalid owner customization/);
    assert.equal(requests.length, before);
  });

  test("historical four-image batches remain visible and eligible for project sharing", () => {
    const generation = { status: 'completed', images: Array.from({ length: 4 }, (_, id) => ({ id })), charged_credits: 4 };
    assert.equal(ui.isOwnerGalleryBatch(generation.images, ui.OWNER_GENERATION_CONTRACT, 4), true);
    assert.equal(service.ownerGenerationStatusMessage(generation), '');
    const html = renderToStaticMarkup(React.createElement(ui.OwnerGenerationImages, { generation }));
    assert.equal((html.match(/class="ai-image-card"/g) || []).length, 4);
    assert.match(html, /Your 4 images are ready/);
    assert.equal(ui.isOwnerGalleryBatch(generation.images, ui.OWNER_GENERATION_CONTRACT, 8), false);
  });

  test("owner entitlement summary displays server credits, dates and limits", () => {
    const html = renderToStaticMarkup(React.createElement(ui.OwnerEntitlementSummary, {
      contract: { batchSize: 8, batchCost: 8 },
      entitlement: {
        plan: "trial",
        remaining_credits: 76,
        batch_cost: 8,
        subscription_end: "2026-11-19T10:00:00",
        generation_allowed: true,
        previous_subscription_expired: false,
        max_projects: 10,
        max_share_links: 20,
      },
    }));
    for (const text of ["Free Trial", "76", "8 credits", "Trial expires", "10 editable projects", "20 active share links"]) {
      assert.ok(html.includes(text), text);
    }
  });

  test("owner entitlement summary explains every generation-disabled entitlement reason", () => {
    const messages = [
      ["subscription_required", /Choose an owner subscription/],
      ["onboarding_required", /Complete Studio Owner setup/],
      ["insufficient_credits", /At least 8 credits are required/],
      ["paid_activation_disabled", /Paid Pro generation is unavailable/],
      ["unrecognized_reason", /unavailable under your owner subscription/],
    ];
    for (const [reason, expected] of messages) {
      const html = renderToStaticMarkup(React.createElement(ui.OwnerEntitlementSummary, {
      contract: { batchSize: 8, batchCost: 8 },
        entitlement: {
          plan: "trial",
          remaining_credits: 100,
          batch_cost: 8,
          generation_allowed: false,
          reason,
          previous_subscription_expired: false,
          max_projects: 10,
          max_share_links: 20,
        },
      }));
      assert.match(html, expected, reason);
    }
  });

  test("editable linked plan enables generation when project and entitlement IDs have different types", () => {
    const plan = { id: 10, project_id: "1" };
    const project = { id: 1, is_editable: true };
    const entitlement = {
      plan: "trial",
      generation_allowed: true,
      batch_cost: 8,
      remaining_credits: 100,
    };

    assert.equal(String(plan.id), "10");
    assert.equal(ui.linkedProjectIsEditable(plan.project_id, project), true);
    assert.equal(ui.ownerGenerationAllowed(entitlement, { batchSize: 8, batchCost: 8 }), true);
    assert.equal(
      ui.linkedProjectIsEditable(plan.project_id, { id: 2, is_editable: true }),
      false,
    );
    assert.equal(
      ui.linkedProjectIsEditable(plan.project_id, { id: 1, is_editable: false }),
      false,
    );
  });

  test("live generation requires explicit eight-credit confirmation and disables unaffordable submission", () => {
    const confirmed = renderToStaticMarkup(React.createElement(ui.OwnerGenerationConfirmation, {
      contract: { batchSize: 8, batchCost: 8 },
      entitlement: { remaining_credits: 16, batch_cost: 8, generation_allowed: true },
      busy: false,
    }));
    assert.ok(confirmed.includes("aria-label=\"Generation charge confirmation\""));
    assert.ok(confirmed.includes("reserves 8 credits"));
    assert.ok(confirmed.includes("Available now: 16 credits"));
    assert.ok(confirmed.includes("Confirm and generate (8 credits)"));
    const insufficient = renderToStaticMarkup(React.createElement(ui.OwnerGenerationConfirmation, {
      contract: { batchSize: 8, batchCost: 8 },
      entitlement: { remaining_credits: 2, batch_cost: 8, generation_allowed: false },
      busy: false,
    }));
    assert.match(insufficient, /Confirm and generate \(8 credits\)<\/button>/);
    assert.match(insufficient, /disabled=""/);
  });

  test("eight-image owner mock renders eight cards with an individual camera guide on every card", () => {
    const setup = {
      camera_height: "At seated eye level",
      camera_distance: "About two metres",
      camera_direction_and_tilt: "Keep the camera level",
      suggested_lens_or_zoom: "Use 2x optical zoom",
      lighting_direction: "Soft light from the left",
      subject_position: "Turn slightly toward the camera",
      steps: ["Position the camera.", "Check the light.", "Frame the subject.", "Focus on the eyes.", "Take the image."],
    };
    const images = Array.from({ length: 8 }, (_, index) => ({
      id: index + 1,
      guidance: {
        pose_name: `Pose ${index + 1}`,
        camera_angle: "Eye level",
        shot_type: "Portrait",
        camera_position: "In front",
        instructions: "Relax the shoulders.",
        camera_setup: setup,
      },
    }));
    const html = renderToStaticMarkup(React.createElement(ui.OwnerGenerationImages, {
      generation: { status: "completed", images, charged_credits: 8, remaining_credits: 12 },
      contract: { batchSize: 8, batchCost: 8 },
    }));
    assert.equal((html.match(/class="ai-image-card"/g) || []).length, 8);
    assert.equal((html.match(/Camera Setup Guide/g) || []).length, 8);
    assert.ok(html.includes("Your 8 images are ready"));
    assert.ok(html.includes("8 credits charged"));
    assert.equal(renderToStaticMarkup(React.createElement(ui.OwnerGenerationImages, {
      generation: { status: "completed", images: images.slice(0, 7) },
      contract: { batchSize: 8, batchCost: 8 },
    })), "");
    assert.equal(renderToStaticMarkup(React.createElement(ui.OwnerGenerationImages, {
      generation: { status: "owner_reserved", images },
      contract: { batchSize: 8, batchCost: 8 },
    })), "");
  });

  test("eight-credit confirmation is explicit and backend contract mismatch disables generation", () => {
    const contract = { batchSize: 8, batchCost: 8 };
    const confirmed = renderToStaticMarkup(React.createElement(ui.OwnerGenerationConfirmation, {
      contract: { batchSize: 8, batchCost: 8 },
      entitlement: { remaining_credits: 16, batch_cost: 8, generation_allowed: true },
      busy: false,
      contract,
    }));
    assert.ok(confirmed.includes("This batch generates 8 images and reserves 8 credits"));
    assert.ok(confirmed.includes("Available now: 16 credits"));
    assert.ok(confirmed.includes("Confirm and generate (8 credits)"));
    assert.doesNotMatch(confirmed, /disabled=""/);

    const currentBackend = { remaining_credits: 100, batch_cost: 4, generation_allowed: true };
    const disabled = renderToStaticMarkup(React.createElement(ui.OwnerGenerationConfirmation, {
      contract: { batchSize: 8, batchCost: 8 },
      entitlement: currentBackend,
      busy: false,
      contract,
    }));
    assert.match(disabled, /disabled=""/);
    const summary = renderToStaticMarkup(React.createElement(ui.OwnerEntitlementSummary, {
      contract: { batchSize: 8, batchCost: 8 },
      entitlement: currentBackend,
      contract,
    }));
    assert.match(summary, /Generation is unavailable/);
    assert.equal(ui.isOwnerGalleryBatch(Array.from({ length: 4 }), contract, 4), true);
    assert.equal(ui.isOwnerGalleryBatch(Array.from({ length: 8 }), contract, 8), true);
    assert.equal(ui.isOwnerGalleryBatch(Array.from({ length: 7 }), contract, 8), false);
    assert.equal(ui.isOwnerGalleryBatch(Array.from({ length: 4 }), contract, 8), false);
  });

  test("subscription cards keep Pro disabled and display the agreed catalogue values", () => {
    const plans = [
      { code: "basic", name: "Free Basic", currency: "LKR", price: "0", credits: 10, max_projects: 2, max_share_links: 3, activation_available: true },
      { code: "trial", name: "Free Trial", currency: "LKR", price: "0", credits: 100, max_projects: 10, max_share_links: 20, trial_days: 14, credit_period: "trial_total", activation_available: true },
      { code: "pro", name: "Paid Pro", currency: "LKR", price: "1500", credits: 500, max_projects: 50, max_share_links: 100, activation_available: false },
    ];
    const html = renderToStaticMarkup(React.createElement(MemoryRouter, null,
      React.createElement(ui.PlanCards, { plans, status: { plan: "basic", trial_available: true }, activate() {} })));
    for (const text of ["10 credits per month", "2 active/editable projects", "3 active share links",
      "100 credits total", "14 days", "20 active share links", "500 credits per month",
      "50 active/editable projects", "100 active share links", "LKR 1,500/month", "Paid activation unavailable"]) {
      assert.ok(html.includes(text), text);
    }
  });
} finally {
  test.after(() => rm(temporary, { recursive: true, force: true }));
}
