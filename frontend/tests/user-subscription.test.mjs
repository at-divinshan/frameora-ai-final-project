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
      contents: `export { SubscriptionPlanCards, StudioOwnerUpgradeCard } from "./src/pages/user/Subscription.jsx";
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
    api, USER_SUBSCRIPTION_PLANS, SubscriptionPlanCards, StudioOwnerUpgradeCard,
    FreeRequestExhaustedNotice, upgradeUserToOwner,
  } = await import(pathToFileURL(outfile));
  assert.deepEqual(USER_SUBSCRIPTION_PLANS, [
    { name: "Starter", price: 1, credits: 20 },
    { name: "Plus", price: 2, credits: 50 },
    { name: "Premium", price: 3, credits: 100 },
  ]);
  const plans = renderToStaticMarkup(React.createElement(SubscriptionPlanCards));
  for (const name of ["Starter", "Plus", "Premium", "$1", "$2", "$3", "20 AI credits", "50 AI credits", "100 AI credits"]) {
    assert.ok(plans.includes(name), `Missing plan detail: ${name}`);
  }
  assert.equal((plans.match(/disabled=""/g) || []).length, 3);
  assert.equal((plans.match(/Subscribe — checkout unavailable/g) || []).length, 3);
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
