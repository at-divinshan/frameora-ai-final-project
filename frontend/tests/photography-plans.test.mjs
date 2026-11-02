import assert from "node:assert/strict";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { build } from "esbuild";

const frontendDirectory = process.cwd();
const temporaryDirectory = await mkdtemp(path.join(frontendDirectory, "tests/.photography-plans-"));

try {
  const buildOptions = {
    absWorkingDir: frontendDirectory,
    bundle: true,
    format: "esm",
    platform: "node",
    packages: "external",
    define: { "import.meta.env": JSON.stringify({ VITE_API_URL: "http://localhost:8000" }) },
  };
  await build({
    ...buildOptions,
    entryPoints: ["src/components/photography/PlanForm.jsx"],
    outfile: path.join(temporaryDirectory, "planForm.js"),
    jsx: "automatic",
  });
  await build({
    ...buildOptions,
    stdin: {
      contents: 'export { createPlan, getMyPlans } from "./src/services/planService.js"; export { default as api } from "./src/services/api.js";',
      resolveDir: frontendDirectory,
      sourcefile: "plan-service-test-entry.js",
    },
    outfile: path.join(temporaryDirectory, "planService.js"),
  });
  await build({
    ...buildOptions,
    entryPoints: ["src/components/photography/PlanCard.jsx"],
    outfile: path.join(temporaryDirectory, "planCard.js"),
    jsx: "automatic",
  });
  const { default: PlanCard } = await import(pathToFileURL(path.join(temporaryDirectory, "planCard.js")).href);
  const { validatePhotographyPlanForm, buildPlanPreferences } = await import(
    pathToFileURL(path.join(temporaryDirectory, "planForm.js")).href
  );
  const { default: React } = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const { default: PlanForm } = await import(
    pathToFileURL(path.join(temporaryDirectory, "planForm.js")).href
  );
  const { createPlan, getMyPlans, api } = await import(
    pathToFileURL(path.join(temporaryDirectory, "planService.js")).href
  );

  const renderCard = preferences => renderToStaticMarkup(React.createElement(PlanCard, {
    plan: { photography_type: "Portrait", environment: "Outdoor", people_count: 2, preferences },
  }));
  test("cards render object and JSON-string preferences as expandable labeled values", () => {
    const preferences = { photography_style: "Cinematic", lighting_preference: "Golden Hour",
      pose_preference: "Candid", camera_angle_preference: "Eye Level", outfit_color: "Blue" };
    const html = renderCard(preferences);
    assert.equal(renderCard(JSON.stringify(preferences)), html);
    assert.match(html, /<details[^>]*><summary>Preferences<\/summary><dl/);
    for (const label of ["Photography Style", "Lighting", "Pose", "Camera Angle", "Outfit Color"]) assert.ok(html.includes(`<dt>${label}</dt>`));
    for (const value of Object.values(preferences)) assert.ok(html.includes(`<dd>${value}</dd>`));
    assert.ok(!html.includes("<pre")); assert.ok(!html.includes("<code"));
    assert.ok(!html.includes("photography_style"));
    assert.ok(!html.includes(">Edit<")); assert.ok(!html.includes(">Delete<"));
  });
  test("cards omit empty and malformed preferences without crashing", () => {
    for (const value of [null, undefined, "", "{broken", "null", "[]", "42", [], {},
      { photography_style: null, lighting_preference: "  ", pose_preference: "", outfit_color: {} }]) {
      assert.ok(!renderCard(value).includes("<details"));
    }
    const html = renderCard({ photography_style: " Natural ", lighting_preference: null, unknown: "secret" });
    assert.ok(html.includes("<dd>Natural</dd>")); assert.ok(!html.includes("<dt>Lighting</dt>"));
    assert.ok(!html.includes("secret"));
    assert.ok(renderCard({ outfit_color: "<script>alert(1)</script>" }).includes("&lt;script&gt;"));
    assert.ok(!renderCard({ outfit_color: "<script>alert(1)</script>" }).includes("<script>"));
  });

  test("validates form fields and converts selected preferences into an API JSON value", () => {
    const valid = {
      photography_type: "Portrait",
      people_count: "10",
      environment: "Outdoor",
      location: "",
      photography_style: "Cinematic",
      lighting_preference: "Golden Hour",
      pose_preference: "Candid",
      camera_angle_preference: "Eye Level",
      outfit_color: "Blue",
    };
    assert.deepEqual(validatePhotographyPlanForm(valid), {});
    assert.deepEqual(buildPlanPreferences(valid), {
      photography_style: "Cinematic",
      lighting_preference: "Golden Hour",
      pose_preference: "Candid",
      camera_angle_preference: "Eye Level",
      outfit_color: "Blue",
    });
    assert.deepEqual(buildPlanPreferences({
      photography_style: "",
      lighting_preference: "",
      pose_preference: "",
      camera_angle_preference: "",
      outfit_color: " ",
    }), null);
    assert.ok(validatePhotographyPlanForm({ ...valid, photography_type: "" }).photography_type);
    assert.ok(validatePhotographyPlanForm({ ...valid, people_count: "11" }).people_count);
    assert.ok(validatePhotographyPlanForm({ ...valid, environment: "x".repeat(21) }).environment);
    assert.ok(validatePhotographyPlanForm({ ...valid, location: "x".repeat(256) }).location);
  });

  test("renders all ten number choices and labeled preference controls", async () => {
    const html = renderToStaticMarkup(React.createElement(PlanForm, { onSubmit: async () => {} }));
    const dashboardStyles = await readFile("src/styles/dashboard.css", "utf8");
    for (let count = 1; count <= 10; count += 1) {
      assert.match(html, new RegExp(`<option[^>]*value="${count}"[^>]*>${count}</option>`));
    }
    for (const label of ["Photography Style", "Lighting Preference", "Pose Preference", "Camera Angle Preference", "Outfit Color"]) {
      assert.ok(html.includes(label));
    }
    assert.ok(!html.includes("JSON"));
    assert.ok(!html.includes('placeholder="{'));
    assert.match(dashboardStyles, /\.user-plan-form \.input-wrapper select\s*\{[^}]*width:\s*100%;[^}]*min-width:\s*0;/);
    assert.match(dashboardStyles, /\[data-theme="dark"\].*color-scheme:\s*dark/);
    assert.match(dashboardStyles, /\[data-theme="light"\].*color-scheme:\s*light/);
    assert.match(dashboardStyles, /select option\s*\{[^}]*color:\s*#f5f7ff;[^}]*background-color:\s*#062039/);
    assert.match(dashboardStyles, /\[data-theme="light"\].*select option\s*\{[^}]*color:\s*#101633;[^}]*background-color:\s*#f0f6ff/);
  });

  test("plan service sends create and list requests to the authenticated plans API", async () => {
    const requests = [];
    api.defaults.adapter = async (config) => {
      requests.push(config);
      return { data: config.method === "post" ? { id: 21 } : [], status: 200, headers: {}, config };
    };
    const values = {
      photography_type: "Portrait",
      people_count: 2,
      environment: "Outdoor",
      location: null,
      shoot_datetime: null,
      preferences: null,
    };
    assert.deepEqual(await createPlan(values), { id: 21 });
    assert.deepEqual(await getMyPlans(), []);
    assert.equal(requests[0].method, "post");
    assert.equal(requests[0].url, "/plans");
    assert.deepEqual(JSON.parse(requests[0].data), values);
    assert.equal(requests[1].method, "get");
    assert.equal(requests[1].url, "/plans");
  });
} finally {
  await rm(temporaryDirectory, { recursive: true, force: true });
}
