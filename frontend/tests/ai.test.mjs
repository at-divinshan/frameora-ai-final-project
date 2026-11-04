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
  await generateImages({planId: 7, description: "Portrait in a garden", reference: new Blob(["test"], {type:"image/png"})});
  assert.equal(requests[0].url, "/ai/generations");
  assert.equal(requests[0].data.get("plan_id"), "7");
  assert.equal(requests[0].data.get("description"), "Portrait in a garden");
  assert.equal(requests[0].data.get("reference").type, "image/png");
  assert.equal(requests[0].headers.Authorization, "Bearer test-session-only");
  assert.notEqual(requests[0].headers["Content-Type"], "application/json");
  await getGeneratedImage(8);
  assert.equal(requests[1].url, "/ai/images/8");
  assert.equal(requests[1].responseType, "blob");
  assert.equal(requests[1].headers.Authorization, "Bearer test-session-only");
  await getGenerations(undefined, 4);
  assert.equal(requests[2].params.before, 4);
  let calls = 0;
  api.defaults.adapter = async () => { calls++; throw new Error("timeout"); };
  await assert.rejects(generateImages({planId:7,description:"Portrait"}));
  assert.equal(calls, 1);
  assert.match(generationError({}), /gallery/);
  assert.equal(generationError({response:{data:{detail:"Service unavailable"}}}), "Service unavailable");
} finally { await rm(temporary, {recursive:true, force:true}); }
