import { mkdir, copyFile, writeFile } from "node:fs/promises";
const target = new URL("../../src/notideck/static/api-docs/", import.meta.url);
await mkdir(target, { recursive: true });
for (const name of [
  "swagger-ui-bundle.js",
  "swagger-ui.css",
  "swagger-ui-bundle.js.LICENSE.txt",
  "LICENSE",
  "NOTICE",
])
  await copyFile(
    new URL("../node_modules/swagger-ui-dist/" + name, import.meta.url),
    new URL(name, target),
  );
await writeFile(
  new URL("init.js", target),
  "window.onload = () => SwaggerUIBundle({url:'/api/openapi.json',dom_id:'#swagger-ui',deepLinking:true,presets:[SwaggerUIBundle.presets.apis]});\n",
);
