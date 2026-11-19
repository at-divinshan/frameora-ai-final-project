import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";

const temporary = await mkdtemp(path.join(process.cwd(), "tests/.user-subscription-"));
try {
  const outfile = path.join(temporary, "subscription.mjs");
  await build({
    stdin: {
      contents: `export { SubscriptionPlanCards, StudioOwnerUpgradeCard, SubscriptionStatus } from "./src/pages/user/Subscription.jsx";
        export { FreeRequestExhaustedNotice } from "./src/pages/user/AIGenerator.jsx";
        export { USER_SUBSCRIPTION_PLANS } from "./src/config/userSubscriptionPlans.js";
        export { upgradeUserToOwner } from "./src/services/authService.js";
        export { default as api } from "./src/services/api.js";`,
      resolveDir: process.cwd(),
    },
    bundle: true,
    format: "esm",
    platform: "node",
    packages: "external",
    outfile,
    jsx: "automatic",
    loader: { ".css": "empty" },
    define: { "import.meta.env": JSON.stringify({ VITE_API_URL: "http://localhost:8000" }) },
  });
  const {
    api, USER_SUBSCRIPTION_PLANS, SubscriptionPlanCards, StudioOwnerUpgradeCard, SubscriptionStatus,
    FreeRequestExhaustedNotice, upgradeUserToOwner,
  } = await import(pathToFileURL(outfile));
  assert.deepEqual(USER_SUBSCRIPTION_PLANS, [
    { code: "free", name: "Free", currency: "LKR", price: 0, credits: 0, free_images: 4 },
    { code: "starter", name: "Starter", currency: "LKR", price: 490, credits: 40 },
    { code: "pro", name: "Pro", currency: "LKR", price: 990, credits: 100 },
  ]);
  const plans = renderToStaticMarkup(React.createElement(SubscriptionPlanCards));
  for (const detail of ["Free", "Starter", "Pro", "LKR 0", "LKR 490", "LKR 990", "4 generated images once per account", "40 AI credits", "100 AI credits"]) {
    assert.ok(plans.includes(detail), `Missing plan detail: ${detail}`);
  }
  assert.equal((plans.match(/disabled=""/g) || []).length, 3);
  assert.equal((plans.match(/Payment setup pending/g) || []).length, 2);
  assert.ok(plans.includes('Included — once per account'));
  assert.doesNotMatch(plans, /Premium|Plus|\$[123]/);
  const exhausted = renderToStaticMarkup(
    React.createElement(MemoryRouter, null, React.createElement(FreeRequestExhaustedNotice)),
  );
  assert.ok(exhausted.includes("Free Generation Limit Reached"));
  assert.ok(exhausted.includes('href="/user/subscription"'));
  assert.ok(exhausted.includes(">View Plans</a>"));
  assert.ok(!exhausted.includes("Generate four images"));
  const ownerUpgrade = renderToStaticMarkup(React.createElement(StudioOwnerUpgradeCard, {
    onUpgrade() {},
    busy: false,
    error: "",
  }));
  assert.ok(ownerUpgrade.includes("Upgrade to Studio Owner"));
  assert.ok(ownerUpgrade.includes("Free Basic: 10 credits per month"));
  assert.ok(ownerUpgrade.includes("one-time Free Trial: 100 credits for 14 days"));
  assert.ok(!ownerUpgrade.includes('disabled=""'));

  for (const plan of ['starter', 'pro']) {
    const status = { plan, period_end: '2027-01-01T00:00:00' };
    const active = renderToStaticMarkup(React.createElement(SubscriptionPlanCards, {
      readiness: {checkout_available:true, paid_activation_available:true}, status,
    }));
    assert.equal((active.match(/Current Plan</g) || []).length, 2);
    assert.equal((active.match(/is-current/g) || []).length, 1);
    assert.ok(active.includes('subscription-current-label'));
    assert.equal((active.match(/disabled=""/g) || []).length, 3);
    assert.ok(active.includes('Available After Your Current Plan Ends'));
    const blocked = renderToStaticMarkup(React.createElement(StudioOwnerUpgradeCard, { status }));
    assert.ok(blocked.includes('disabled=""'));
    assert.ok(blocked.includes('Paid credits cannot be transferred'));
  }
  const expired = renderToStaticMarkup(React.createElement(SubscriptionPlanCards, {
    readiness: {checkout_available:true, paid_activation_available:true}, status: {plan:'free'},
  }));
  assert.equal((expired.match(/Continue to Stripe Test Checkout/g) || []).length, 2);

  const summary = renderToStaticMarkup(React.createElement(SubscriptionStatus, {status:{plan:'starter',remaining_credits:0,period_end:'2027-01-01T00:00:00'}}));
  assert.ok(summary.includes('Starter'));
  assert.ok(summary.includes('>0</dd>'));
  assert.ok(summary.includes('2027'));
  const unavailable = renderToStaticMarkup(React.createElement(SubscriptionStatus, {status:{plan:'free'}}));
  assert.equal((unavailable.match(/Not available/g)||[]).length, 2);
  const actualCost = renderToStaticMarkup(React.createElement(SubscriptionPlanCards, {status:{plan:'starter',credits_per_batch:4}}));
  assert.ok(actualCost.includes('4 credits per four-image batch'));
  const requests = [];
  api.defaults.adapter = async (config) => {
    requests.push(config);
    return { data: { user: { id: "7", role: "owner" } }, status: 200, statusText: "OK", headers: {}, config };
  };
  await upgradeUserToOwner({ remember_me: true });
  assert.equal(requests[0].method, "post");
  assert.equal(requests[0].url, "/users/me/upgrade-to-owner");
  assert.deepEqual(JSON.parse(requests[0].data), { remember_me: true });
} finally {
  await rm(temporary, { recursive: true, force: true });
}
