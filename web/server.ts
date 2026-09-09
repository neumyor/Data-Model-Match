import { basename, join, normalize, resolve } from "node:path";
import { mkdir, rm, stat } from "node:fs/promises";

type JsonObject = Record<string, unknown>;

type MatchRequest = {
  source: JsonObject;
  target: JsonObject;
  timeoutMs?: number;
};

type ServerEvent = { event: string; data: JsonObject };

const webRoot = import.meta.dir;
const projectRoot = resolve(webRoot, "..");
const staticRoot = join(webRoot, "dist");
const staticRoots = [staticRoot, webRoot];
const examplesRoot = join(projectRoot, "examples");
const configPath = join(projectRoot, "config.llm.json");
const workspaceConfigPath = join(projectRoot, "config.workspace.json");
const defaultResourceStorePath = join(projectRoot, ".datamodelmatch");
const maxBodyBytes = 5 * 1024 * 1024;
const defaultTimeoutMs = 90_000;
const maxTimeoutMs = 180_000;
let configuredApiKey = "";
let resourceStorePath = defaultResourceStorePath;

const mimeTypes: Record<string, string> = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".svg": "image/svg+xml",
  ".woff2": "font/woff2",
};
const publicExtensions = new Set(Object.keys(mimeTypes).concat([".gif", ".ico", ".jpeg", ".jpg", ".png", ".webp"]));

function jsonResponse(body: JsonObject, status = 200): Response {
  return Response.json(body, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

function errorResponse(code: string, message: string, status: number): Response {
  return jsonResponse({ error: { code, message } }, status);
}

function toSafeMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  const redacted = configuredApiKey
    ? message.replace(configuredApiKey, "[已隐藏]")
    : message;
  return redacted
    .replace(/Bearer\s+\S+/gi, "Bearer [已隐藏]")
    .replace(/\bsk-[A-Za-z0-9_-]+\b/g, "[已隐藏]")
    .slice(0, 1_000);
}

async function parseConfigStatus(): Promise<JsonObject> {
  const file = Bun.file(configPath);
  if (!file.size) {
    return { configured: false, reason: "未找到本地 LLM 配置文件" };
  }

  try {
    const config: unknown = await file.json();
    if (!isObject(config)) {
      return { configured: false, reason: "本地 LLM 配置格式无效" };
    }

    const endpoint = typeof config.endpoint === "string" ? config.endpoint : "";
    const apiKey = typeof config.apiKey === "string" ? config.apiKey : "";
    const model = typeof config.model === "string" ? config.model : "";
    const stream = config.stream === undefined ? false : config.stream;
    configuredApiKey = apiKey;
    let secureEndpoint = false;
    try {
      secureEndpoint = new URL(endpoint).protocol === "https:";
    } catch {
      secureEndpoint = false;
    }
    const valid = Boolean(endpoint && apiKey && model && secureEndpoint && stream === false);

    return valid
      ? {
          configured: true,
          model,
          endpoint: redactEndpoint(endpoint),
          stream,
        }
      : {
          configured: false,
          reason: !secureEndpoint
            ? "本地 LLM 配置的服务地址必须使用 HTTPS"
            : stream === true
              ? "本地 LLM 配置不支持开启模型流式模式"
              : "本地 LLM 配置缺少必要字段",
        };
  } catch {
    return { configured: false, reason: "本地 LLM 配置格式无效" };
  }
}

async function loadWorkspaceSettings(): Promise<void> {
  const file = Bun.file(workspaceConfigPath);
  if (!file.size) return;
  try {
    const value: unknown = await file.json();
    if (isObject(value) && typeof value.resourceStorePath === "string") {
      resourceStorePath = validateWorkspacePath(value.resourceStorePath);
    }
  } catch {
    resourceStorePath = defaultResourceStorePath;
  }
}

function validateWorkspacePath(value: string): string {
  const raw = value.trim();
  if (!raw) {
    throw new RequestError("INVALID_WORKSPACE_PATH", "资源工作区路径不能为空", 400);
  }
  const path = resolve(raw);
  const protectedRoots = [
    resolve(projectRoot, ".git"),
    resolve(projectRoot, "_reference_only"),
  ];
  if (protectedRoots.some((root) => path === root || path.startsWith(`${root}/`))) {
    throw new RequestError(
      "PROTECTED_WORKSPACE_PATH",
      "资源工作区不能设置在 .git 或 _reference_only 目录中",
      400,
    );
  }
  return path;
}

async function workspaceStatus(): Promise<JsonObject> {
  const root = resourceStorePath;
  const datasetPath = join(root, "resources", "datasets");
  const modelPath = join(root, "resources", "models");
  let exists = false;
  try {
    exists = (await stat(root)).isDirectory();
  } catch {
    exists = false;
  }
  return {
    resourceStorePath: root,
    datasetPath,
    modelPath,
    exists,
    isDefault: root === defaultResourceStorePath,
  };
}

async function saveWorkspaceSettings(path: string): Promise<JsonObject> {
  resourceStorePath = validateWorkspacePath(path);
  await Bun.write(
    workspaceConfigPath,
    JSON.stringify({ resourceStorePath }, null, 2) + "\n",
  );
  return workspaceStatus();
}

function redactEndpoint(endpoint: string): string {
  try {
    const url = new URL(endpoint);
    return `${url.protocol}//${url.host}/...`;
  } catch {
    return "已配置";
  }
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseTimeout(value: unknown): number {
  if (value === undefined) {
    return defaultTimeoutMs;
  }

  if (typeof value !== "number" || !Number.isFinite(value) || value < 1_000) {
    throw new RequestError("INVALID_TIMEOUT", "timeoutMs 必须是不小于 1000 的毫秒数", 400);
  }

  return Math.min(Math.floor(value), maxTimeoutMs);
}

async function readMatchRequest(request: Request): Promise<MatchRequest> {
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > maxBodyBytes) {
    throw new RequestError("PAYLOAD_TOO_LARGE", "请求体不能超过 5 MB", 413);
  }

  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > maxBodyBytes) {
    throw new RequestError("PAYLOAD_TOO_LARGE", "请求体不能超过 5 MB", 413);
  }

  let payload: unknown;
  try {
    payload = JSON.parse(raw);
  } catch {
    throw new RequestError("INVALID_JSON", "请求体必须是合法 JSON", 400);
  }

  if (!isObject(payload) || !isObject(payload.source) || !isObject(payload.target)) {
    throw new RequestError("INVALID_INPUT", "请求体必须包含对象类型的 source 和 target", 400);
  }

  return {
    source: payload.source,
    target: payload.target,
    timeoutMs: parseTimeout(payload.timeoutMs),
  };
}

async function readJsonObject(request: Request): Promise<JsonObject> {
  const contentLength = Number(request.headers.get("content-length") ?? "0");
  if (Number.isFinite(contentLength) && contentLength > maxBodyBytes) {
    throw new RequestError("PAYLOAD_TOO_LARGE", "请求体不能超过 5 MB", 413);
  }
  const raw = await request.text();
  if (new TextEncoder().encode(raw).byteLength > maxBodyBytes) {
    throw new RequestError("PAYLOAD_TOO_LARGE", "请求体不能超过 5 MB", 413);
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new RequestError("INVALID_JSON", "请求体必须是合法 JSON", 400);
  }
  if (!isObject(value)) {
    throw new RequestError("INVALID_INPUT", "请求体必须是 JSON 对象", 400);
  }
  return value;
}

class RequestError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function serializeEvent(event: ServerEvent): Uint8Array {
  return new TextEncoder().encode(`event: ${event.event}\ndata: ${JSON.stringify(event.data)}\n\n`);
}

function resourceCommand(args: string[]): string[] {
  return [
    process.env.PYTHON ?? "python3",
    "-m",
    "datamodelmatch.resource_cli",
    "--store",
    resourceStorePath,
    ...args,
  ];
}

async function runResourceJson(args: string[]): Promise<JsonObject> {
  const child = Bun.spawn(resourceCommand(args), {
    cwd: projectRoot,
    env: { ...process.env, PYTHONPATH: "src" },
    stdout: "pipe",
    stderr: "pipe",
  });
  const [exitCode, stdout, stderr] = await Promise.all([
    child.exited,
    new Response(child.stdout).text(),
    new Response(child.stderr).text(),
  ]);
  if (exitCode !== 0) {
    let message = toSafeMessage(stderr.trim()) || "资源服务执行失败";
    try {
      const parsed = JSON.parse(stderr);
      if (isObject(parsed) && isObject(parsed.error) && typeof parsed.error.message === "string") {
        message = parsed.error.message;
      }
    } catch {
      // Use the sanitized stderr message.
    }
    throw new RequestError("RESOURCE_COMMAND_FAILED", message, 400);
  }
  const value: unknown = JSON.parse(stdout);
  if (!isObject(value)) {
    throw new Error("资源服务返回格式无效");
  }
  return value;
}

function runResourceStream(args: string[], cleanupPath?: string): Response {
  let child: ReturnType<typeof Bun.spawn> | undefined;
  let cancelled = false;
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      let sawEnd = false;
      const send = (event: string, data: JsonObject) => {
        if (!closed) controller.enqueue(serializeEvent({ event, data }));
      };
      try {
        child = Bun.spawn(resourceCommand(args), {
          cwd: projectRoot,
          env: { ...process.env, PYTHONPATH: "src" },
          stdout: "pipe",
          stderr: "pipe",
        });
        const reader = child.stdout.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!cancelled) {
          const chunk = await reader.read();
          if (chunk.done) break;
          buffer += decoder.decode(chunk.value, { stream: true });
          const lines = buffer.split(/\r?\n/);
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.trim()) continue;
            const envelope: unknown = JSON.parse(line);
            if (!isObject(envelope) || typeof envelope.event !== "string" || !isObject(envelope.data)) {
              throw new Error("资源任务返回了无效事件");
            }
            if (envelope.event === "end") sawEnd = true;
            send(envelope.event, envelope.data);
          }
        }
        const exitCode = await child.exited;
        const stderr = toSafeMessage(await new Response(child.stderr).text());
        if (!cancelled && exitCode !== 0 && !sawEnd) {
          send("error", { code: "RESOURCE_TASK_FAILED", message: stderr || "资源任务执行失败" });
          send("end", { status: "failed" });
        } else if (!cancelled && !sawEnd) {
          send("end", { status: "completed" });
        }
      } catch (error) {
        if (!cancelled) {
          send("error", { code: "RESOURCE_STREAM_FAILED", message: toSafeMessage(error) });
          send("end", { status: "failed" });
        }
      } finally {
        if (cleanupPath) {
          await rm(cleanupPath, { force: true });
        }
        if (!closed) {
          closed = true;
          controller.close();
        }
      }
    },
    cancel() {
      cancelled = true;
      if (child?.exitCode === null) child.kill();
    },
  });
  return new Response(stream, {
    headers: {
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "content-type": "text/event-stream; charset=utf-8",
      "x-accel-buffering": "no",
    },
  });
}

async function runMatch(request: Request, payload: MatchRequest): Promise<Response> {
  const requestId = crypto.randomUUID();
  const tempDirectory = join(projectRoot, ".tmp", "web-match", requestId);
  const timeoutMs = payload.timeoutMs ?? defaultTimeoutMs;
  let childProcess: ReturnType<typeof Bun.spawn> | undefined;
  let timeoutHandle: ReturnType<typeof setTimeout> | undefined;
  let progressHandle: ReturnType<typeof setInterval> | undefined;
  let closed = false;
  let cancelled = false;
  let timedOut = false;

  const cleanUp = async () => {
    if (timeoutHandle) {
      clearTimeout(timeoutHandle);
      timeoutHandle = undefined;
    }
    if (progressHandle) {
      clearInterval(progressHandle);
      progressHandle = undefined;
    }
    if (childProcess && childProcess.exitCode === null) {
      childProcess.kill();
    }
    await rm(tempDirectory, { recursive: true, force: true });
  };

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const send = (event: ServerEvent) => {
        if (!closed) {
          controller.enqueue(serializeEvent(event));
        }
      };
      const finish = async (status: "completed" | "failed" | "cancelled") => {
        if (closed) {
          return;
        }
        send({ event: "end", data: { status } });
        closed = true;
        controller.close();
        await cleanUp();
      };

      try {
        if (cancelled) return;
        await mkdir(tempDirectory, { recursive: true });
        if (cancelled) return;
        send({
          event: "stage",
          data: { stage: "validate", label: "检查请求结构", status: "started" },
        });
        send({
          event: "stage",
          data: { stage: "validate", label: "检查请求结构", status: "completed" },
        });
        send({
          event: "stage",
          data: { stage: "prepare", label: "创建隔离任务", status: "started" },
        });
        await Bun.write(join(tempDirectory, "source.json"), JSON.stringify(payload.source, null, 2));
        await Bun.write(join(tempDirectory, "target.json"), JSON.stringify(payload.target, null, 2));
        if (cancelled) return;
        send({
          event: "stage",
          data: { stage: "prepare", label: "创建隔离任务", status: "completed" },
        });
        send({
          event: "log",
          data: { level: "info", message: "输入已写入隔离任务目录，正在启动匹配引擎。" },
        });

        childProcess = Bun.spawn(
          [
            process.env.PYTHON ?? "python3",
            "-m",
            "datamodelmatch.cli",
            join(tempDirectory, "source.json"),
            join(tempDirectory, "target.json"),
            "--config",
            configPath,
            "--timeout",
            String(Math.max(1, Math.floor(timeoutMs / 1_000))),
          ],
          {
            cwd: projectRoot,
            env: { ...process.env, PYTHONPATH: "src" },
            stdout: "pipe",
            stderr: "pipe",
          },
        );
        if (cancelled) {
          childProcess.kill();
          return;
        }
        const stdoutPromise = new Response(childProcess.stdout).text();
        const stderrPromise = new Response(childProcess.stderr).text();

        timeoutHandle = setTimeout(() => {
          timedOut = true;
          childProcess?.kill();
        }, timeoutMs);

        send({
          event: "stage",
          data: { stage: "agent", label: "智能体分析字段语义", status: "started" },
        });
        send({
          event: "log",
          data: { level: "info", message: "已发起真实大语言模型请求，响应通过事件流持续报告。" },
        });

        let elapsedSeconds = 0;
        progressHandle = setInterval(() => {
          elapsedSeconds += 5;
          send({
            event: "log",
            data: {
              level: "info",
              message: `智能体仍在分析字段语义，已等待 ${elapsedSeconds} 秒。`,
            },
          });
        }, 5_000);

        const [exitCode, stdout, stderr] = await Promise.all([
          childProcess.exited,
          stdoutPromise,
          stderrPromise,
        ]);
        if (progressHandle) {
          clearInterval(progressHandle);
          progressHandle = undefined;
        }

        if (timedOut) {
          send({
            event: "error",
            data: { code: "TIMEOUT", message: `匹配请求在 ${timeoutMs} 毫秒后超时。` },
          });
          await finish("failed");
          return;
        }

        if (exitCode !== 0) {
          const message = toSafeMessage(stderr.replace(/^error:\s*/i, "").trim());
          send({
            event: "error",
            data: { code: "MATCH_FAILED", message: message || "模型匹配服务执行失败。" },
          });
          await finish("failed");
          return;
        }

        let result: unknown;
        try {
          result = JSON.parse(stdout);
        } catch {
          send({
            event: "error",
            data: { code: "INVALID_RESULT", message: "匹配服务返回了无效的结构化结果。" },
          });
          await finish("failed");
          return;
        }

        if (!isObject(result)) {
          send({
            event: "error",
            data: { code: "INVALID_RESULT", message: "匹配服务返回结果格式无效。" },
          });
          await finish("failed");
          return;
        }

        send({
          event: "stage",
          data: { stage: "agent", label: "智能体分析字段语义", status: "completed" },
        });
        send({
          event: "stage",
          data: { stage: "candidate", label: "接收结构化候选映射", status: "started" },
        });
        send({
          event: "stage",
          data: { stage: "candidate", label: "接收结构化候选映射", status: "completed" },
        });
        send({
          event: "stage",
          data: { stage: "verify", label: "校验映射结果", status: "started" },
        });
        send({
          event: "stage",
          data: { stage: "verify", label: "校验映射结果", status: "completed" },
        });
        send({
          event: "stage",
          data: { stage: "complete", label: "完成", status: "started" },
        });
        send({ event: "result", data: { result } });
        send({
          event: "stage",
          data: { stage: "complete", label: "完成", status: "completed" },
        });
        await finish("completed");
      } catch (error) {
        send({
          event: "error",
          data: { code: "SERVER_ERROR", message: toSafeMessage(error) || "匹配服务发生未知错误。" },
        });
        await finish("failed");
      }
    },
    async cancel() {
      cancelled = true;
      closed = true;
      await cleanUp();
    },
  });

  return new Response(stream, {
    headers: {
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "content-type": "text/event-stream; charset=utf-8",
      "x-accel-buffering": "no",
    },
  });
}

async function serveStatic(request: Request): Promise<Response> {
  let pathname: string;
  try {
    pathname = decodeURIComponent(new URL(request.url).pathname);
  } catch {
    return new Response("请求路径无效", { status: 400 });
  }
  const requestedPath = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
  const extension = requestedPath.slice(requestedPath.lastIndexOf("."));

  if (requestedPath.startsWith("examples/")) {
    const examplePath = normalize(join(examplesRoot, requestedPath.slice("examples/".length)));
    if (examplePath.startsWith(`${examplesRoot}/`) && extension === ".json") {
      const file = Bun.file(examplePath);
      if (file.size) {
        return new Response(file, {
          headers: {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store, max-age=0",
          },
        });
      }
    }
  }

  if (publicExtensions.has(extension)) {
    for (const root of staticRoots) {
      const candidate = normalize(join(root, requestedPath));
      if (!candidate.startsWith(`${root}/`) && candidate !== root) {
        continue;
      }
      const file = Bun.file(candidate);
      if (file.size) {
        return new Response(file, {
          headers: {
            "content-type": mimeTypes[extension] ?? "application/octet-stream",
            "cache-control": "no-store, max-age=0",
          },
        });
      }
    }
  }

  if (!basename(requestedPath).includes(".")) {
    for (const root of staticRoots) {
      const index = Bun.file(join(root, "index.html"));
      if (index.size) {
        return new Response(index, {
          headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store, max-age=0" },
        });
      }
    }
  }

  if (requestedPath === "index.html") {
    return new Response(
      "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>DataModelMatch</title><body><main><h1>前端正在构建</h1><p>本地匹配服务已启动，等待静态页面产物。</p></main></body></html>",
      { status: 200, headers: { "content-type": "text/html; charset=utf-8" } },
    );
  }

  return new Response("未找到资源", { status: 404, headers: { "content-type": "text/plain; charset=utf-8" } });
}

await loadWorkspaceSettings();

const port = Number(process.env.PORT ?? "3000");

const server = Bun.serve({
  port: Number.isFinite(port) && port > 0 ? port : 3000,
  // The default Bun idle timeout can terminate an SSE response while the real LLM is working.
  idleTimeout: 255,
  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === "/api/config-status" && request.method === "GET") {
      return jsonResponse(await parseConfigStatus());
    }

    if (url.pathname === "/api/workspace" && request.method === "GET") {
      return jsonResponse(await workspaceStatus());
    }

    if (url.pathname === "/api/workspace" && request.method === "PUT") {
      try {
        const body = await readJsonObject(request);
        const path = typeof body.resourceStorePath === "string"
          ? body.resourceStorePath
          : "";
        return jsonResponse(await saveWorkspaceSettings(path));
      } catch (error) {
        if (error instanceof RequestError) {
          return errorResponse(error.code, error.message, error.status);
        }
        return errorResponse("WORKSPACE_SAVE_FAILED", toSafeMessage(error), 500);
      }
    }

    if (
      (url.pathname === "/api/search/datasets" || url.pathname === "/api/search/models")
      && request.method === "GET"
    ) {
      const query = url.searchParams.get("q")?.trim() ?? "";
      if (!query) {
        return errorResponse("INVALID_QUERY", "请输入搜索关键词", 400);
      }
      try {
        const kind = url.pathname.endsWith("datasets") ? "dataset" : "model";
        return jsonResponse(await runResourceJson(["search", kind, query, "--limit", "8"]));
      } catch (error) {
        if (error instanceof RequestError) {
          return errorResponse(error.code, error.message, error.status);
        }
        return errorResponse("SEARCH_FAILED", toSafeMessage(error), 502);
      }
    }

    if (url.pathname === "/api/resources" && request.method === "GET") {
      const kind = url.searchParams.get("kind");
      if (kind && kind !== "dataset" && kind !== "model") {
        return errorResponse("INVALID_KIND", "资源类型必须是 dataset 或 model", 400);
      }
      try {
        const args = ["list"];
        if (kind) args.push("--kind", kind);
        return jsonResponse(await runResourceJson(args));
      } catch (error) {
        return errorResponse("LIST_FAILED", toSafeMessage(error), 500);
      }
    }

    if (url.pathname === "/api/resources/import") {
      if (request.method !== "POST") {
        return errorResponse("METHOD_NOT_ALLOWED", "该接口只支持 POST 请求", 405);
      }
      try {
        const body = await readJsonObject(request);
        const kind = typeof body.kind === "string" ? body.kind : "";
        const sourceType = typeof body.sourceType === "string" ? body.sourceType : "";
        const source = typeof body.source === "string" ? body.source.trim() : "";
        const revision = typeof body.revision === "string" && body.revision.trim()
          ? body.revision.trim()
          : "";
        const downloadMode = typeof body.downloadMode === "string"
          ? body.downloadMode
          : "sample";
        const maxBytes = typeof body.maxBytes === "number"
          ? Math.floor(body.maxBytes)
          : 50 * 1024 * 1024;
        if (!["dataset", "model"].includes(kind) || !sourceType || !source) {
          throw new RequestError(
            "INVALID_INPUT",
            "导入请求必须包含有效的 kind、sourceType 和 source",
            400,
          );
        }
        if (!["metadata", "sample", "full"].includes(downloadMode)) {
          throw new RequestError("INVALID_DOWNLOAD_MODE", "下载模式无效", 400);
        }
        if (maxBytes < 1 || maxBytes > 500 * 1024 * 1024) {
          throw new RequestError("INVALID_SIZE_LIMIT", "下载上限必须在 1 字节到 500 MB 之间", 400);
        }
        return runResourceStream([
          "import",
          kind,
          sourceType,
          source,
          "--revision",
          revision,
          "--download-mode",
          downloadMode,
          "--max-bytes",
          String(maxBytes),
        ]);
      } catch (error) {
        if (error instanceof RequestError) {
          return errorResponse(error.code, error.message, error.status);
        }
        return errorResponse("IMPORT_FAILED", toSafeMessage(error), 500);
      }
    }

    const resourceMatch = url.pathname.match(/^\/api\/resources\/([A-Za-z0-9_-]+)$/);
    if (resourceMatch) {
      const resourceId = resourceMatch[1];
      try {
        if (request.method === "GET") {
          return jsonResponse(await runResourceJson(["get", resourceId]));
        }
        if (request.method === "DELETE") {
          return jsonResponse(await runResourceJson(["delete", resourceId]));
        }
        return errorResponse("METHOD_NOT_ALLOWED", "该资源接口只支持 GET 或 DELETE", 405);
      } catch (error) {
        if (error instanceof RequestError) {
          return errorResponse(error.code, error.message, error.status);
        }
        return errorResponse("RESOURCE_FAILED", toSafeMessage(error), 500);
      }
    }

    if (url.pathname === "/api/compatibility") {
      if (request.method !== "POST") {
        return errorResponse("METHOD_NOT_ALLOWED", "该接口只支持 POST 请求", 405);
      }
      try {
        const body = await readJsonObject(request);
        const datasetId = typeof body.datasetResourceId === "string"
          ? body.datasetResourceId
          : "";
        const modelId = typeof body.modelResourceId === "string"
          ? body.modelResourceId
          : "";
        const timeoutMs = parseTimeout(body.timeoutMs);
        if (!datasetId || !modelId) {
          throw new RequestError(
            "INVALID_INPUT",
            "兼容性分析需要 datasetResourceId 和 modelResourceId",
            400,
          );
        }
        return runResourceStream([
          "compatibility",
          datasetId,
          modelId,
          "--config",
          configPath,
          "--timeout",
          String(Math.floor(timeoutMs / 1_000)),
        ]);
      } catch (error) {
        if (error instanceof RequestError) {
          return errorResponse(error.code, error.message, error.status);
        }
        return errorResponse("COMPATIBILITY_FAILED", toSafeMessage(error), 500);
      }
    }

    if (url.pathname === "/api/dataset-transform") {
      if (request.method !== "POST") {
        return errorResponse("METHOD_NOT_ALLOWED", "该接口只支持 POST 请求", 405);
      }
      let reportPath = "";
      try {
        const body = await readJsonObject(request);
        const datasetId = typeof body.datasetResourceId === "string" ? body.datasetResourceId : "";
        const modelId = typeof body.modelResourceId === "string" ? body.modelResourceId : "";
        const report = isObject(body.report) ? body.report : null;
        if (!datasetId || !modelId || !report) {
          throw new RequestError(
            "INVALID_INPUT",
            "转换请求需要 datasetResourceId、modelResourceId 和 report",
            400,
          );
        }
        if (report.status !== "adaptable") {
          throw new RequestError(
            "INVALID_REPORT_STATUS",
            "只有状态为“转换后可用”的兼容性报告可以生成适配数据集",
            400,
          );
        }
        const requestId = crypto.randomUUID();
        reportPath = join(projectRoot, ".tmp", "web-transform", `${requestId}.json`);
        await mkdir(join(projectRoot, ".tmp", "web-transform"), { recursive: true });
        await Bun.write(reportPath, JSON.stringify(report, null, 2));
        return runResourceStream(
          [
            "transform-dataset",
            datasetId,
            modelId,
            reportPath,
          ],
          reportPath,
        );
      } catch (error) {
        if (reportPath) {
          await rm(reportPath, { force: true });
        }
        if (error instanceof RequestError) {
          return errorResponse(error.code, error.message, error.status);
        }
        return errorResponse("TRANSFORM_FAILED", toSafeMessage(error), 500);
      }
    }

    if (url.pathname === "/api/match") {
      if (request.method !== "POST") {
        return errorResponse("METHOD_NOT_ALLOWED", "该接口只支持 POST 请求", 405);
      }
      try {
        return await runMatch(request, await readMatchRequest(request));
      } catch (error) {
        if (error instanceof RequestError) {
          return errorResponse(error.code, error.message, error.status);
        }
        return errorResponse("INTERNAL_ERROR", "服务端暂时无法处理匹配任务", 500);
      }
    }

    return serveStatic(request);
  },
});

console.log(`DataModelMatch 本地服务已启动：http://localhost:${server.port}`);
