import { cp, mkdir, rm } from "node:fs/promises";
import { join } from "node:path";

const root = import.meta.dir;
const out = join(root, "dist");

await rm(out, { recursive: true, force: true });
await mkdir(out, { recursive: true });
await cp(join(root, "index.html"), join(out, "index.html"));
await cp(join(root, "styles.css"), join(out, "styles.css"));
await cp(join(root, "app.js"), join(out, "app.js"));
await cp(join(root, "..", "examples"), join(out, "examples"), { recursive: true });

console.log(`前端静态资源已构建到 ${out}`);
