import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";

const temporary = await mkdtemp(path.join(process.cwd(), "tests/.ai-"));
try {
  const outfile = path.join(temporary, "service.mjs");
  await build({
    stdin: { contents: 'export * from "./src/services/aiService.js"; export {default as api, setAccessToken} from "./src/services/api.js";', resolveDir: process.cwd() },
    bundle: true, format: "esm", platform: "node", packages: "external", outfile,
    define: { "import.meta.env": JSON.stringify({ VITE_API_URL: "http://localhost:8000" }) },
  });
  const { api, setAccessToken, generateImages, getGeneratedImage, getGenerations, generationError } = await import(pathToFileURL(outfile));
  const requests = [];
  api.defaults.adapter = async (config) => {
    requests.push(config);
    return {data: {id: 1}, status: 200, statusText: "OK", headers: {}, config};
  };
  setAccessToken("test-session-only");
  await generateImages({planId: 7, description: "Portrait in a garden", reference: new Blob(["test"], {type:"image/png"}), backgroundReference: new Blob(["scene"], {type:"image/webp"})});
  assert.equal(requests[0].url, "/ai/generations");
  assert.equal(requests[0].data.get("plan_id"), "7");
  assert.equal(requests[0].data.get("description"), "Portrait in a garden");
  assert.equal(requests[0].data.get("reference").type, "image/png");
  assert.equal(requests[0].data.get("background_reference").type, "image/webp");
  assert.equal(requests[0].headers.Authorization, "Bearer test-session-only");
  assert.notEqual(requests[0].headers["Content-Type"], "application/json");
  await getGeneratedImage(8);
  assert.equal(requests[1].url, "/ai/images/8");
  assert.equal(requests[1].responseType, "blob");
  assert.equal(requests[1].headers.Authorization, "Bearer test-session-only");
  await getGenerations(undefined, 4);
  assert.equal(requests[2].params.before, 4);
  await generateImages({planId: 7});
  assert.equal(requests[3].data.get("description"), "");
  const componentOutput = path.join(temporary, "components.mjs");
  await build({
    stdin: { contents: 'export {default as Uploader} from "./src/components/ai/ImageUploader.jsx";export {default as Loader} from "./src/components/ai/GenerationLoader.jsx"; export {default as Card} from "./src/components/ai/GeneratedImageCard.jsx";', resolveDir: process.cwd() },
    bundle: true, format: "esm", platform: "node", packages: "external", outfile: componentOutput, jsx: "automatic",
    define: { "import.meta.env": JSON.stringify({ VITE_API_URL: "http://localhost:8000" }) },
  });
  const { Loader, Card, Uploader } = await import(pathToFileURL(componentOutput));
  const { default: React } = await import("react");
  const { renderToStaticMarkup } = await import("react-dom/server");
  const uploads = renderToStaticMarkup(React.createElement(React.Fragment, null,
    React.createElement(Uploader, {id:'person',value:{name:'person.png'},onChange:()=>{}}),
    React.createElement(Uploader, {id:'background',background:true,value:{name:'scene.png'},onChange:()=>{}})));
  assert.match(uploads,/Person Reference Image/);assert.match(uploads,/Background Reference Image/);
  assert.match(uploads,/Remove person image/);assert.match(uploads,/Remove background image/);
  assert.match(uploads,/id="person"/);assert.match(uploads,/id="background"/);
  const loader = renderToStaticMarkup(React.createElement(Loader));
  assert.equal((loader.match(/ai-skeleton-card/g) || []).length, 4);
  const ownerLoader = renderToStaticMarkup(React.createElement(Loader, {imageCount: 8}));
  assert.equal((ownerLoader.match(/ai-skeleton-card/g) || []).length, 8);
  assert.ok(ownerLoader.includes("Creating 8 photography concepts"));
  assert.ok(ownerLoader.includes("all 8 images are saved"));
  assert.ok(loader.includes('role="status"'));
  assert.ok(loader.includes('aria-busy="true"'));
  assert.ok(!loader.includes("%"));
  const guidance = { pose_name: "Seated portrait", camera_angle: "Low Angle", shot_type: "Medium portrait", camera_position: "Camera at waist height", instructions: "Rest hands on knees." };
  const card = renderToStaticMarkup(React.createElement(Card, {image: {id: 1, guidance}, index: 0}));
  for (const value of Object.values(guidance)) assert.ok(card.includes(value));
  assert.ok(card.includes("has not been visually verified"));
  const setup = {
    camera_height: "Suggested height: at seated eye level.",
    camera_distance: "Approximate starting distance: 1.5–3 metres.",
    camera_direction_and_tilt: "Face the subject from 45 degrees and keep the camera level.",
    suggested_lens_or_zoom: "Suggested 2× optical zoom, if available; approximate framing only.",
    lighting_direction: "Use soft light from the front-left.",
    subject_position: "Rest hands on the lap and turn the face toward the lens.",
    steps: ["Stand 45 degrees to the subject.", "Hold the phone at seated eye level.",
      "Keep the phone level and point toward the face.", "Start about two metres away.",
      "Ask the subject to relax their hands.", "Frame the torso and light the face from the side.",
      "Tap the nearest eye to focus and capture a few images."],
  };
  const detailedCard = renderToStaticMarkup(React.createElement(Card, {image: {id: 3, guidance: {...guidance, camera_setup: setup}}, index: 2}));
  for (const value of Object.values(setup).flat()) assert.ok(detailedCard.includes(value));
  assert.match(detailedCard, /<details class="ai-camera-guide"><summary>Camera Setup Guide/);
  assert.equal((detailedCard.match(/<li>/g) || []).length, 7);
  assert.ok(detailedCard.includes("7 practical steps"));
  assert.ok(detailedCard.includes("has not been visually verified"));
  assert.ok(card.includes("A detailed camera setup guide was not saved"));
  assert.ok(!card.includes("<ol>"));
  const escaped = renderToStaticMarkup(React.createElement(Card, {image: {id: 4, guidance: {...guidance, camera_setup: {...setup, subject_position: "<script>unsafe</script>"}}}, index: 3}));
  assert.ok(escaped.includes("&lt;script&gt;"));
  assert.ok(!escaped.includes("<script>"));
  const legacy = renderToStaticMarkup(React.createElement(Card, {image: {id: 2}, index: 1}));
  assert.ok(legacy.includes("guidance was not saved"));
  let calls = 0;
  api.defaults.adapter = async () => { calls++; throw new Error("timeout"); };
  await assert.rejects(generateImages({planId:7,description:"Portrait"}));
  assert.equal(calls, 1);
  assert.match(generationError({}), /gallery/);
  assert.equal(generationError({response:{data:{detail:"Service unavailable"}}}), "Service unavailable");
} finally { await rm(temporary, {recursive:true, force:true}); }
