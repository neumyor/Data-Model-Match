(function () {
  "use strict";

  var state = {
    view: "datasets",
    resources: { dataset: [], model: [] },
    loading: { dataset: false, model: false },
    drawerKind: "dataset",
    selectedResource: null,
    running: false,
    trace: [],
    toastTimer: null,
    report: null,
    reportContext: null,
    workspace: {
      resourceStorePath: "",
      datasetPath: "",
      modelPath: ""
    },
    transform: {
      running: false,
      context: null,
      resource: null,
      status: "idle"
    },
    discovery: { running: false }
  };
  var labels = {
    dataset: { title: "数据集", empty: "还没有数据集。添加 Hugging Face 来源或本地目录，开始建立资源描述。" },
    model: { title: "模型", empty: "还没有模型。添加 GitHub 仓库或本地目录，开始提取模型契约。" }
  };
  var statusLabels = {
    discovering: "发现中", awaiting_confirmation: "待确认", downloading: "下载中",
    scanning: "扫描中", profiling: "解析中", needs_review: "待复核", ready: "已就绪", failed: "失败"
  };
  var stageNames = {
    discover: "识别资源", acquire: "拉取原始资源", scan: "扫描目录结构",
    profile: "生成结构化描述", evidence: "整理证据", compare: "比对兼容性",
    recommend: "生成转换建议", verify: "校验分析结论", complete: "完成",
    prepare: "准备转换任务", transform: "转换数据文件",
    discovering: "识别资源", downloading: "拉取原始资源", scanning: "扫描目录结构",
    profiling: "生成结构化描述", deterministic: "确定性契约检查",
    llm: "大语言模型补充分析", result: "生成兼容性报告"
  };
  var traceStageNames = {
    discover: "读取资源信息",
    acquire: "准备资源快照",
    scan: "检查数据结构",
    profile: "整理资源描述",
    evidence: "汇总分析证据",
    compare: "比对模型输入契约",
    recommend: "生成转换建议",
    verify: "复核分析结果",
    complete: "整理兼容性结论"
  };
  var traceStageMessages = {
    discover: "正在读取数据集和模型的结构化描述",
    acquire: "正在准备本次分析所需的资源快照",
    scan: "正在检查字段、类型和输入形状",
    profile: "正在整理可用于匹配的资源描述",
    evidence: "正在汇总字段契约和解析证据",
    compare: "正在比对模型输入契约",
    recommend: "正在生成转换建议",
    verify: "正在复核字段映射和兼容性结论",
    complete: "兼容性分析已完成"
  };
  var dimensionNames = {
    task: "任务类型", modality: "数据模态", input_fields: "输入字段",
    data_types: "数据类型", shape: "张量形状", preprocessing: "预处理",
    labels: "标签可用性", license: "许可证", runtime: "运行环境"
  };
  var evidenceNames = {
    readme: "说明文档", dependency_file: "依赖声明", framework: "框架识别",
    task_hint: "任务识别", inventory: "文件清单", static_schema: "静态结构",
    repository_metadata: "仓库元数据", resolved_revision: "固定版本"
  };

  function $(id) { return document.getElementById(id); }
  function all(selector) { return Array.prototype.slice.call(document.querySelectorAll(selector)); }
  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
  function formatTime() {
    var d = new Date();
    return [d.getHours(), d.getMinutes(), d.getSeconds()].map(function (n) { return String(n).padStart(2, "0"); }).join(":");
  }
  function formatBytes(value) {
    var bytes = Number(value || 0);
    if (!bytes) return "未统计";
    if (bytes < 1024) return Math.round(bytes) + " 字节";
    if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
    return (bytes / 1024 / 1024 / 1024).toFixed(1) + " GB";
  }
  function formatDate(value) {
    if (!value) return "时间未知";
    var date = new Date(value);
    return Number.isNaN(date.getTime()) ? "时间未知" : date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  }
  function normalizeList(payload, key) {
    if (Array.isArray(payload)) return payload;
    if (!payload || typeof payload !== "object") return [];
    return Array.isArray(payload[key]) ? payload[key] : Array.isArray(payload.items) ? payload.items : Array.isArray(payload.resources) ? payload.resources : [];
  }
  function normalizeResource(item, kind) {
    var resource = item && item.resource ? Object.assign({}, item.resource, { profile: item.profile || item.resource.profile }) : Object.assign({}, item || {});
    resource.kind = resource.kind || kind;
    resource.warnings = Array.isArray(resource.warnings) ? resource.warnings : [];
    resource.profile = resource.profile || {};
    resource.profile.warnings = Array.isArray(resource.profile.warnings) ? resource.profile.warnings : [];
    return resource;
  }
  function profileOf(resource) { return resource.profile || {}; }
  function warningItems(resource) {
    var values = (resource.warnings || []).concat(profileOf(resource).warnings || []);
    var seen = {};
    return values.filter(function (item) {
      var key = typeof item === "string" ? item : JSON.stringify(item);
      if (seen[key]) return false;
      seen[key] = true;
      return true;
    });
  }
  function evidenceText(item) {
    if (typeof item === "string") return item;
    var label = evidenceNames[item.kind] || "解析证据";
    return label + "：" + (item.detail || item.message || item.path || item.source || "已记录");
  }
  function sourceLabel(resource) {
    var source = resource.source;
    if (source && typeof source === "object") source = source.location || source.url || source.path;
    return source || resource.localPath || "本地资源";
  }
  function completeness(resource) {
    var value = Number(profileOf(resource).completeness);
    return Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0));
  }
  function resourceDescription(resource) {
    var profile = profileOf(resource);
    return profile.description || resource.description || (resource.kind === "dataset" ? "尚未生成数据集描述。" : "尚未生成模型契约描述。");
  }
  function provenanceOf(resource) {
    return resource.provenance || profileOf(resource).provenance || {};
  }
  function isAiReadyDataset(resource) {
    if (!resource || resource.kind !== "dataset") return false;
    var provenance = provenanceOf(resource);
    return (
      resource.sourceType === "derived" ||
      (provenance.sourceDatasetName &&
        provenance.targetModelName &&
        provenance.transformStatus === "completed")
    );
  }
  function statusClass(status) {
    if (status === "ready") return "ready";
    if (["downloading", "scanning", "profiling", "discovering"].indexOf(status) >= 0) return "running";
    if (status === "needs_review" || status === "awaiting_confirmation") return "warning";
    if (status === "failed") return "failed";
    return "neutral";
  }
  function statusText(status) { return statusLabels[status] || (status ? "处理中" : "未知状态"); }
  function tagsFor(resource) {
    var profile = profileOf(resource);
    return (resource.kind === "dataset" ? (profile.modalities || []).concat(profile.taskHints || []) : (profile.frameworks || []).concat(profile.tasks || [])).slice(0, 4);
  }
  function showToast(message) {
    var toast = $("toast");
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(function () { toast.classList.remove("show"); }, 3600);
  }
  function setService(text, mode) {
    $("serviceStatus").className = "service-status " + (mode || "");
    $("serviceStatus").innerHTML = "<b></b>" + escapeHtml(text);
  }
  async function request(url, options) {
    var response = await fetch(url, options);
    if (!response.ok) {
      var body = await response.json().catch(function () { return null; });
      throw new Error(body && (body.message || body.error && (body.error.message || body.error)) || "服务返回状态码 " + response.status);
    }
    return response;
  }

  async function loadResources(kind) {
    state.loading[kind] = true;
    renderResourceGrid(kind);
    try {
      var response = await request("/api/resources?kind=" + encodeURIComponent(kind));
      var payload = await response.json();
      state.resources[kind] = normalizeList(payload, kind).map(function (item) { return normalizeResource(item, kind); });
      setService("服务已连接", "ready");
    } catch (error) {
      state.resources[kind] = [];
      setService("资源接口未连接", "warn");
      showToast(labels[kind].title + "列表加载失败：" + error.message);
    } finally {
      state.loading[kind] = false;
      renderResourceGrid(kind);
      populateResourceSelects();
    }
  }
  function renderSummary(kind) {
    var items = state.resources[kind];
    var ready = items.filter(function (item) { return item.status === "ready"; }).length;
    var reviewing = items.filter(function (item) { return item.status !== "ready" && item.status !== "failed"; }).length;
    var warnings = items.reduce(function (sum, item) { return sum + warningItems(item).length; }, 0);
    var target = $(kind === "dataset" ? "datasetSummary" : "modelSummary");
    target.innerHTML = '<div class="summary-stat"><strong>' + items.length + '</strong><span>个资源</span></div><span class="summary-rule"></span><div class="summary-stat"><strong>' + ready + '</strong><span>已就绪</span></div><span class="summary-rule"></span><div class="summary-stat"><strong>' + reviewing + '</strong><span>处理中</span></div><span class="summary-rule"></span><div class="summary-stat"><strong>' + warnings + '</strong><span>条提醒</span></div>';
  }
  function renderResourceGrid(kind) {
    renderSummary(kind);
    var target = $(kind === "dataset" ? "datasetGrid" : "modelGrid");
    if (state.loading[kind]) {
      target.innerHTML = '<div class="loading-card"><div><span></span>正在读取资源目录</div></div>';
      return;
    }
    var items = state.resources[kind];
    if (!items.length) {
      target.innerHTML = '<div class="empty-resource"><div class="empty-state"><span class="empty-symbol">＋</span><p>' + labels[kind].empty + '</p><button class="primary-button" type="button" data-add-kind="' + kind + '">添加' + labels[kind].title + "</button></div></div>";
      bindDynamicButtons();
      return;
    }
    target.innerHTML = items.map(function (resource, index) {
      var profile = profileOf(resource);
      var warningCount = warningItems(resource).length;
      var tags = tagsFor(resource);
      var pct = Math.round(completeness(resource) * 100);
      var provenance = provenanceOf(resource);
      var aiReady = isAiReadyDataset(resource);
      var derivedFrom = kind === "dataset" && provenance.sourceDatasetName
        ? '<div class="card-derived">适配自 ' + escapeHtml(provenance.sourceDatasetName) + " · 面向 " + escapeHtml(provenance.targetModelName || "目标模型") + "</div>"
        : "";
      return '<article class="resource-card ' + (kind === "model" ? "model-card" : "") + (aiReady ? " ai-ready-card" : "") + '" style="animation-delay:' + (index * 45) + 'ms">' +
        '<div class="resource-card-head"><span class="resource-kind"><i class="resource-type-dot ' + (kind === "model" ? "model-dot" : "") + '"></i>' + labels[kind].title + '</span><div class="card-statuses">' + (aiReady ? '<span class="ai-ready-badge"><i></i>AI-Ready</span>' : "") + '<span class="status-pill ' + statusClass(resource.status) + '">' + statusText(resource.status) + "</span></div></div>" +
        '<h3 title="' + escapeHtml(resource.name || resource.source) + '">' + escapeHtml(resource.name || "未命名资源") + "</h3>" +
        '<p class="card-description">' + escapeHtml(resourceDescription(resource)) + "</p>" +
        '<div class="card-source"><span class="source-mark">↗</span><span title="' + escapeHtml(sourceLabel(resource)) + '">' + escapeHtml(sourceLabel(resource)) + "</span></div>" +
        derivedFrom +
        '<div class="card-tags">' + (tags.length ? tags.map(function (tag) { return '<span class="card-tag">' + escapeHtml(tag) + "</span>"; }).join("") : '<span class="card-tag">等待解析</span>') + "</div>" +
        '<div class="completeness"><span>描述完整度 ' + pct + '%</span><b><i style="width:' + pct + '%"></i></b></div>' +
        (warningCount ? '<div class="card-warning">△ ' + warningCount + " 条提醒需要关注</div>" : "") +
        '<div class="resource-card-foot"><span class="card-meta">' + escapeHtml(resource.resolvedRevision || resource.revision || "版本未固定") + " · " + formatBytes(resource.sizeBytes) + " · " + formatDate(resource.updatedAt) + '</span><div class="card-buttons"><button class="text-action" type="button" data-detail-id="' + escapeHtml(resource.id) + '" data-detail-kind="' + kind + '">查看详情</button>' + (resource.status === "ready" ? '<button class="text-action" type="button" data-use-kind="' + kind + '" data-use-id="' + escapeHtml(resource.id) + '">用于匹配</button>' : "") + "</div></div></article>";
    }).join("");
    bindDynamicButtons();
  }
  function bindDynamicButtons() {
    all("[data-add-kind]").forEach(function (button) { button.onclick = function () { openResourceDrawer(button.dataset.addKind); }; });
    all("[data-detail-id]").forEach(function (button) { button.onclick = function () { openDetail(button.dataset.detailKind, button.dataset.detailId); }; });
    all("[data-semantic-analyze]").forEach(function (button) {
      button.onclick = function () { runSemanticAnalysis(button.dataset.semanticAnalyze); };
    });
    all("[data-use-id]").forEach(function (button) {
      button.onclick = function () {
        switchView("match");
        $(button.dataset.useKind === "dataset" ? "datasetSelect" : "modelSelect").value = button.dataset.useId;
        updateSelectMeta(button.dataset.useKind);
      };
    });
  }

  function switchView(view) {
    state.view = view;
    all(".nav-item").forEach(function (button) { button.classList.toggle("active", button.dataset.view === view); });
    all(".view").forEach(function (section) {
      var active = section.id === "view-" + view;
      section.hidden = !active;
      section.classList.toggle("active", active);
    });
    if (view === "match") populateResourceSelects();
  }
  function populateResourceSelects() {
    ["dataset", "model"].forEach(function (kind) {
      var select = $(kind + "Select"), current = select.value;
      var ready = state.resources[kind].filter(function (resource) { return resource.status === "ready"; });
      select.innerHTML = '<option value="">' + (ready.length ? "选择已就绪" + labels[kind].title : "暂无已就绪" + labels[kind].title) + "</option>" + ready.map(function (resource) { return '<option value="' + escapeHtml(resource.id) + '">' + escapeHtml(resource.name || resource.source) + "</option>"; }).join("");
      if (ready.some(function (resource) { return resource.id === current; })) select.value = current;
      updateSelectMeta(kind);
    });
  }
  function selected(kind) {
    var id = $(kind + "Select").value;
    return state.resources[kind].find(function (item) { return item.id === id; }) || null;
  }
  function updateSelectMeta(kind) {
    var resource = selected(kind), meta = $(kind + "SelectMeta");
    meta.textContent = resource ? sourceLabel(resource) + " · " + (resource.resolvedRevision || resource.revision || "版本未固定") + " · " + Math.round(completeness(resource) * 100) + "% 完整" : "需要先选择一个已就绪" + labels[kind].title;
  }

  function openDrawer(id) {
    $("backdrop").hidden = false;
    requestAnimationFrame(function () {
      $("backdrop").classList.add("visible");
      $(id).classList.add("open");
      $(id).setAttribute("aria-hidden", "false");
      document.body.style.overflow = "hidden";
    });
  }
  function closeDrawers() {
    all(".drawer").forEach(function (drawer) { drawer.classList.remove("open"); drawer.setAttribute("aria-hidden", "true"); });
    $("backdrop").classList.remove("visible");
    document.body.style.overflow = "";
    setTimeout(function () { $("backdrop").hidden = true; }, 260);
  }
  function openResourceDrawer(kind) {
    state.drawerKind = kind;
    $("resourceDrawerTitle").textContent = "添加" + labels[kind].title;
    $("sourceInput").value = ""; $("revisionInput").value = ""; $("searchResults").hidden = true; $("searchResults").innerHTML = ""; $("importTrace").hidden = true; resetLocalFolderSelection();
    all("[data-drawer-kind]").forEach(function (button) { button.classList.toggle("active", button.dataset.drawerKind === kind); });
    configureSourceType(kind);
    openDrawer("resourceDrawer");
    setTimeout(function () { if (!$("remoteSourceFields").hidden) $("sourceInput").focus(); }, 280);
  }

  async function searchSource() {
    var query = $("sourceInput").value.trim();
    if (!query) { showToast("请先输入来源地址、仓库 ID 或关键词"); return; }
    var kind = state.drawerKind, selectedType = $("sourceTypeSelect").value;
    var endpoint = kind === "dataset" ? "/api/search/datasets?q=" : "/api/search/models?q=";
    $("searchResults").hidden = false;
    $("searchResults").innerHTML = '<div class="loading-card"><div><span></span>正在搜索候选来源</div></div>';
    try {
      var response = await request(endpoint + encodeURIComponent(query)), payload = await response.json(), results = normalizeList(payload, "results");
      if (!results.length) { $("searchResults").innerHTML = '<div class="field-help">没有找到候选来源，可以直接使用当前输入。</div>'; return; }
      $("searchResults").innerHTML = results.slice(0, 8).map(function (item) {
        var source = item.source || item.id || item.fullName || item.name || query;
        return '<button class="search-result" type="button" data-pick-source="' + escapeHtml(source) + '"><span><strong>' + escapeHtml(item.name || item.id || source) + '</strong><small>' + escapeHtml(source) + (item.description ? " · " + item.description : "") + "</small></span><span class=\"search-pick\">选用</span></button>";
      }).join("");
      all("[data-pick-source]").forEach(function (button) {
        button.onclick = function () { $("sourceInput").value = button.dataset.pickSource; $("searchResults").hidden = true; showToast("已选用候选来源"); };
      });
    } catch (error) {
      $("searchResults").innerHTML = '<div class="field-help">搜索失败，可直接提交当前输入。原因：' + escapeHtml(error.message) + "</div>";
    }
  }

  function resetImportTrace() { $("importTrace").hidden = false; $("importEvents").innerHTML = ""; $("importProgress").textContent = "准备中"; $("importProgressBar").style.width = "0%"; }
  function addImportEvent(message) {
    var target = $("importEvents"), item = document.createElement("div");
    item.className = "import-event"; item.textContent = message; target.appendChild(item); target.scrollTop = target.scrollHeight;
  }
  function applySseProgress(event) {
    var message = event.message || event.label || event.detail || event.content || (event.stage && stageNames[event.stage]) || "收到资源处理事件";
    addImportEvent(message);
    var progress = Number(event.percent || event.progress || event.percentage);
    if (Number.isFinite(progress)) { progress = progress <= 1 ? progress * 100 : progress; $("importProgressBar").style.width = Math.max(0, Math.min(100, progress)) + "%"; $("importProgress").textContent = Math.round(progress) + "%"; }
    else if (event.stage || event.type) $("importProgress").textContent = stageNames[event.stage] || "处理中";
  }
  function parseSseBlock(block) {
    var eventName = (block.match(/^event:\s*(.+)$/m) || [])[1] || "";
    var data = block.split(/\r?\n/).filter(function (line) { return line.indexOf("data:") === 0; }).map(function (line) { return line.slice(5).trim(); }).join("\n");
    if (!data || data === "[DONE]") return null;
    try { var parsed = JSON.parse(data); if (parsed && typeof parsed === "object") parsed.eventName = eventName; return parsed; } catch (error) { return { message: data, eventName: eventName }; }
  }
  async function consumeSse(response, handlers) {
    var contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("text/event-stream") || !response.body) { handlers.data(await response.json()); return; }
    var reader = response.body.getReader(), decoder = new TextDecoder(), buffer = "";
    while (true) {
      var chunk = await reader.read();
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });
      var blocks = buffer.split(/\r?\n\r?\n/); buffer = blocks.pop() || "";
      blocks.forEach(function (block) { var event = parseSseBlock(block); if (event) handlers.event(event); });
    }
    if (buffer.trim()) { var last = parseSseBlock(buffer); if (last) handlers.event(last); }
  }
  function configureSourceType(kind) {
    var select = $("sourceTypeSelect");
    select.innerHTML = kind === "dataset"
      ? '<option value="auto">自动识别（远程）</option><option value="huggingface">Hugging Face 仓库</option><option value="local">本地文件夹</option>'
      : '<option value="auto">自动识别（远程）</option><option value="github">GitHub 仓库</option><option value="local">本地文件夹</option>';
    $("sourceInput").placeholder = kind === "dataset"
      ? "例如：lhoestq/demo1 或 huggingface.co/datasets/..."
      : "例如：karpathy/minGPT 或 github.com/...";
    syncSourceFields();
  }
  function resetLocalFolderSelection() {
    $("localFolderInput").value = "";
    $("localFolderSummary").textContent = "尚未选择文件夹";
  }
  function updateLocalFolderSummary() {
    var files = Array.prototype.slice.call($("localFolderInput").files || []);
    if (!files.length) { $("localFolderSummary").textContent = "尚未选择文件夹"; return; }
    var total = files.reduce(function (sum, file) { return sum + Number(file.size || 0); }, 0);
    var root = (files[0].webkitRelativePath || files[0].name).split(/[\\/]/)[0] || "已选文件夹";
    $("localFolderSummary").textContent = root + " · " + files.length + " 个文件 · " + formatBytes(total);
  }
  function syncSourceFields() {
    var local = $("sourceTypeSelect").value === "local";
    $("remoteSourceFields").hidden = local;
    $("localSourceFields").hidden = !local;
    $("searchResults").hidden = true;
  }
  function buildLocalImportForm() {
    var files = Array.prototype.slice.call($("localFolderInput").files || []);
    if (!files.length) throw new Error("请先选择本地文件夹");
    var firstPath = files[0].webkitRelativePath || "";
    var sourceName = firstPath.split(/[\\/]/)[0];
    if (!sourceName) throw new Error("浏览器未提供所选文件夹信息，请重新选择文件夹");
    var total = 0;
    var manifest = files.map(function (file) {
      var path = file.webkitRelativePath || "";
      var prefix = sourceName + "/";
      if (!path || path.indexOf(prefix) !== 0) throw new Error("所选文件夹包含无效路径，请重新选择");
      total += Number(file.size || 0);
      return { path: path.slice(prefix.length), size: file.size };
    });
    if (total > 500 * 1024 * 1024) throw new Error("本地文件夹超过 500 MB 导入上限");
    var form = new FormData();
    form.append("kind", state.drawerKind);
    form.append("downloadMode", $("downloadMode").value);
    form.append("sourceName", sourceName);
    form.append("manifest", JSON.stringify(manifest));
    files.forEach(function (file) { form.append("files", file, file.name); });
    return form;
  }
  function inferSourceType(source, kind) {
    var selectedType = $("sourceTypeSelect").value;
    if (selectedType && selectedType !== "auto") return selectedType;
    if (/^https?:\/\//i.test(source)) return /github\.com/i.test(source) ? "github" : "huggingface";
    return kind === "model" ? "github" : "huggingface";
  }
  async function importResource() {
    var source = $("sourceInput").value.trim();
    var local = $("sourceTypeSelect").value === "local";
    if (!local && !source) { showToast("请填写资源来源"); return; }
    resetImportTrace(); $("importResource").disabled = true; $("importResource").textContent = "解析中…"; addImportEvent("开始解析资源");
    try {
      var response;
      if (local) {
        response = await request("/api/resources/import-local", {
          method: "POST", headers: { Accept: "text/event-stream, application/json" }, body: buildLocalImportForm()
        });
      } else {
        response = await request("/api/resources/import", {
          method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream, application/json" },
          body: JSON.stringify({ kind: state.drawerKind, sourceType: inferSourceType(source, state.drawerKind), source: source, revision: $("revisionInput").value.trim() || undefined, downloadMode: $("downloadMode").value })
        });
      }
      var result = null, failure = null;
      await consumeSse(response, {
        data: function (data) { result = data.resource ? data : data.result || data; },
        event: function (event) {
          if (event.eventName === "result" || event.result || event.resource) result = event.resource ? event : event.result || event;
          else if (event.eventName === "error" || event.error) failure = event.message || event.error;
          else applySseProgress(event);
        }
      });
      if (failure) throw new Error(typeof failure === "string" ? failure : failure.message || "资源解析失败");
      if (result && (result.id || result.resource)) {
        var resource = normalizeResource(result, state.drawerKind);
        var existing = state.resources[state.drawerKind].findIndex(function (item) { return item.id === resource.id; });
        if (existing >= 0) state.resources[state.drawerKind][existing] = resource; else state.resources[state.drawerKind].unshift(resource);
        $("importProgressBar").style.width = "100%"; $("importProgress").textContent = "已完成"; addImportEvent("资源描述已生成，可以查看详情");
        renderResourceGrid(state.drawerKind); populateResourceSelects(); showToast("已添加" + labels[state.drawerKind].title); setTimeout(closeDrawers, 520);
      } else { addImportEvent("服务已结束，但没有返回资源记录"); showToast("导入完成但缺少资源记录"); }
    } catch (error) { addImportEvent("处理失败：" + error.message); $("importProgress").textContent = "失败"; showToast("资源导入失败：" + error.message); }
    finally { $("importResource").disabled = false; $("importResource").textContent = "开始解析"; }
  }

  async function openDetail(kind, id) {
    state.selectedResource = { kind: kind, id: id };
    $("detailTitle").textContent = "资源详情"; $("detailContent").innerHTML = '<div class="loading-card"><div><span></span>正在读取资源描述</div></div>'; openDrawer("detailDrawer");
    try {
      var response = await request("/api/resources/" + encodeURIComponent(id)), payload = await response.json(), resource = normalizeResource(payload, kind);
      if (kind === "dataset") {
        try {
          var semanticResponse = await request("/api/dataset-semantic-profiles/" + encodeURIComponent(id));
          var semanticPayload = await semanticResponse.json();
          resource.semanticProfile = semanticPayload.profile || null;
        } catch (error) {
          resource.semanticProfile = null;
        }
      }
      state.selectedResource.resource = resource; renderDetail(resource);
    } catch (error) { $("detailContent").innerHTML = '<div class="empty-resource"><div class="empty-state"><span class="empty-symbol">!</span><p>资源详情读取失败：' + escapeHtml(error.message) + "</p></div></div>"; }
  }
  async function runSemanticAnalysis(resourceId) {
    var buttons = all("[data-semantic-analyze]");
    buttons.forEach(function (button) { button.disabled = true; button.textContent = "分析中…"; });
    try {
      var response = await request("/api/dataset-semantic-profiles/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resourceId: resourceId })
      });
      var payload = await response.json();
      if (!payload.profile) throw new Error("服务未返回语义档案");
      showToast("数据集语义分析已完成");
      await openDetail("dataset", resourceId);
    } catch (error) {
      showToast("语义分析失败：" + error.message);
    } finally {
      buttons.forEach(function (button) { button.disabled = false; button.textContent = "生成语义分析"; });
    }
  }
  function semanticProfileSection(profile, resourceId) {
    if (!profile) {
      return '<section class="semantic-section semantic-required" data-testid="semantic-details-root"><div class="semantic-heading"><div><p class="overline">数据集语义</p><h3>语义分析未完成</h3></div><span class="status-pill warning" data-testid="semantic-details-profile-status">需要分析</span></div><p class="detail-description">数据集只有在语义分析完成后才可用于任务发现。请重新执行分析。</p><button class="small-button" type="button" data-semantic-analyze="' + escapeHtml(resourceId) + '" data-testid="semantic-details-reanalyze">重新分析</button></section>';
    }
    var structural = profile.structural || {}, content = profile.content || {}, analysis = profile.agentAnalysis || {};
    var capabilities = Array.isArray(analysis.capabilities) ? analysis.capabilities : (structural.tasks || []);
    var characteristics = Array.isArray(analysis.characteristics) ? analysis.characteristics : [];
    var limitations = Array.isArray(analysis.limitations) ? analysis.limitations : [];
    var unknowns = Array.isArray(profile.unresolved) ? profile.unresolved : [];
    var evidence = Array.isArray(profile.evidence) ? profile.evidence : [];
    var codeExecutions = Array.isArray(profile.agentCodeExecutions) ? profile.agentCodeExecutions.filter(function (item) { return item && typeof item === "object"; }) : [];
    var sampledImages = codeExecutions.reduce(function (total, item) {
      return total + (Array.isArray(item.images) ? item.images.length : 0);
    }, 0);
    var executionItems = codeExecutions.map(function (item, index) {
      var images = Array.isArray(item.images) ? item.images.filter(function (image) { return image && typeof image === "object"; }) : [];
      var summary = typeof item.summary === "string" && item.summary.trim() ? item.summary.trim() : "未提供执行摘要。";
      var artifacts = images.length
        ? "已提交图片：" + images.map(function (image) {
            var path = typeof image.path === "string" ? image.path : "未命名图片";
            var size = Number(image.byteCount);
            return path + (Number.isFinite(size) && size > 0 ? "（" + formatBytes(size) + "）" : "");
          }).join("、")
        : item.imageAvailability === "none_found"
          ? "代码已确认当前本地快照没有可读图片。"
          : "本次未选择图片。";
      return '<li><strong>第 ' + escapeHtml(String(index + 1)) + ' 次本地检查</strong><small>' + escapeHtml(artifacts) + '</small><p>' + escapeHtml(summary) + '</p></li>';
    }).join("");
    var contentText = content.source === "semantic_agent"
      ? (content.description || profile.semanticDescription || "Agent 未提供内容描述。")
      : (content.message || content.reason || "尚未获得内容语义。");
    return '<section class="semantic-section" data-testid="semantic-details-root">' +
      '<div class="semantic-heading"><div><p class="overline">数据集语义</p><h3>Agent 语义分析</h3></div><span class="status-pill compatible" data-testid="semantic-details-profile-status">已完成</span></div>' +
      '<p class="semantic-summary">' + escapeHtml(profile.summary || "已生成语义档案") + '</p>' +
      '<section class="semantic-description" data-testid="semantic-details-content-region"><h4>数据集描述</h4><p>' + escapeHtml(contentText) + '</p></section>' +
      '<section class="semantic-capabilities" data-testid="semantic-details-structure-region"><h4>可支持的任务</h4>' + semanticList(capabilities, "尚未确认可支持的任务") + '</section>' +
      '<div class="semantic-facts"><section><h4>数据特征</h4>' + semanticList(characteristics, "尚未形成明确特征") + '</section><section><h4>使用限制</h4>' + semanticList(limitations, "未发现明确限制") + '</section></div>' +
      '<section class="semantic-agent-execution" data-testid="semantic-details-agent-execution-region"><div><h4>Agent 执行与图片采样</h4><span>' + escapeHtml(String(codeExecutions.length)) + ' 次本地检查 · ' + escapeHtml(String(sampledImages)) + ' 张提交给模型的真实图片</span></div>' + (executionItems ? '<ul data-testid="semantic-details-agent-execution-list">' + executionItems + '</ul>' : '<p>Agent 未执行本地数据检查；请重新分析以生成当前版本的交付记录。</p>') + '</section>' +
      '<section class="semantic-evidence" data-testid="semantic-details-evidence-region"><h4>证据与待确认事项</h4>' + (evidence.length ? '<ul class="evidence-list" data-testid="semantic-details-evidence-list">' + evidence.slice(0, 6).map(function (item) { return '<li>' + escapeHtml((item.id ? item.id + " · " : "") + (item.path || "证据") + " · " + (item.detail || item.kind || "")) + '</li>'; }).join("") + '</ul>' : '<p>没有可展示的证据。</p>') + '<h4 class="semantic-subheading">待确认事项</h4>' + semanticList(unknowns, "没有未解决事项", "semantic-details-unresolved-list") + '</section>' +
      '<button class="text-action semantic-refresh" type="button" data-semantic-analyze="' + escapeHtml(resourceId) + '" data-testid="semantic-details-reanalyze">重新分析</button></section>';
  }
  function semanticList(items, emptyText, testId) {
    var values = Array.isArray(items) ? items.filter(function (item) { return typeof item === "string" && item.trim(); }) : [];
    return values.length ? '<ul' + (testId ? ' data-testid="' + testId + '"' : "") + '>' + values.map(function (item) { return '<li>' + escapeHtml(item) + '</li>'; }).join("") + '</ul>' : '<p>' + escapeHtml(emptyText) + '</p>';
  }
  function renderDetail(resource) {
    var profile = profileOf(resource), kind = resource.kind, warnings = warningItems(resource);
    var provenance = provenanceOf(resource);
    var features = kind === "dataset" ? (profile.features || []) : ((profile.inputContract && profile.inputContract.fields) || []);
    var trace = resource.trace || resource.events || profile.trace || [];
    if (!Array.isArray(trace)) trace = [];
    $("detailTitle").textContent = resource.name || "资源详情";
    $("detailContent").innerHTML = '<div class="detail-title-row"><i class="resource-type-dot ' + (kind === "model" ? "model-dot" : "") + '"></i><div><h3>' + escapeHtml(resource.name || "未命名资源") + '</h3><p>' + escapeHtml(sourceLabel(resource)) + "</p></div><span class=\"status-pill " + statusClass(resource.status) + '">' + statusText(resource.status) + "</span></div>" +
      '<div class="detail-stat-row"><div class="detail-stat"><strong>' + Math.round(completeness(resource) * 100) + '%</strong><small>描述完整度</small></div><div class="detail-stat"><strong>' + (resource.fileCount || "—") + '</strong><small>文件数量</small></div><div class="detail-stat"><strong>' + formatBytes(resource.sizeBytes) + '</strong><small>本地大小</small></div></div>' +
      (kind === "dataset" ? semanticProfileSection(resource.semanticProfile, resource.id) : "") +
      '<div class="detail-section source-details"><h4>' + (kind === "dataset" ? "原始字段与结构" : "输入契约") + '</h4><p class="detail-description">' + escapeHtml(resourceDescription(resource)) + '</p>' + (features.length ? '<table class="detail-table"><thead><tr><th>名称</th><th>类型</th><th>角色</th></tr></thead><tbody>' + features.slice(0, 12).map(function (feature) { return "<tr><td>" + escapeHtml(feature.name || "未命名") + "</td><td>" + escapeHtml(feature.dataType || "未知") + "</td><td>" + escapeHtml(feature.semanticRole || (feature.required ? "必填" : "—")) + "</td></tr>"; }).join("") + "</tbody></table>" : '<p class="detail-description">当前描述中还没有可展示的字段契约。</p>') + "</div>" +
      '<div class="detail-section source-details"><h4>来源与版本</h4><p class="detail-description">' + escapeHtml((resource.resolvedRevision || resource.revision || "版本未固定") + " · 最近更新 " + formatDate(resource.updatedAt)) + "</p></div>" +
      (kind === "dataset" && provenance.sourceDatasetName ? '<div class="detail-section provenance-section"><h4>适配来源</h4><div class="provenance-grid"><div><span>来源数据集</span><strong>' + escapeHtml(provenance.sourceDatasetName) + '</strong></div><div><span>适配模型</span><strong>' + escapeHtml(provenance.targetModelName || "—") + '</strong></div><div><span>转换状态</span><strong class="provenance-status">' + escapeHtml(provenance.transformStatus === "completed" ? "已完成" : provenance.transformStatus || "处理中") + "</strong></div></div></div>" : "") +
      '<div class="detail-section"><h4>执行轨迹</h4>' + (trace.length ? '<ul class="evidence-list">' + trace.slice(-10).map(function (item) { return "<li>" + escapeHtml(typeof item === "string" ? item : item.message || item.detail || item.stage || JSON.stringify(item)) + "</li>"; }).join("") + "</ul>" : '<p class="detail-description">暂无导入记录。</p>') + "</div>" +
      (profile.evidence && profile.evidence.length ? '<div class="detail-section"><h4>解析证据</h4><ul class="evidence-list">' + profile.evidence.slice(0, 8).map(function (item) { return "<li>" + escapeHtml(evidenceText(item)) + "</li>"; }).join("") + "</ul></div>" : "") +
      (warnings.length ? '<div class="detail-section"><h4>需要关注</h4><ul class="warning-list">' + warnings.map(function (item) { return "<li>" + escapeHtml(typeof item === "string" ? item : item.message || JSON.stringify(item)) + "</li>"; }).join("") + "</ul></div>" : "");
    bindDynamicButtons();
  }

  function renderTaskDiscovery(payload) {
    var matches = Array.isArray(payload.matches) ? payload.matches : [];
    $("taskDiscoveryCount").textContent = matches.length + " 个数据集";
    if (!matches.length) {
      $("taskDiscoveryResults").innerHTML = '<div class="empty-resource"><div class="empty-state compact"><span class="empty-symbol">○</span><p>当前没有可分析的数据集。</p></div></div>';
      return;
    }
    $("taskDiscoveryResults").innerHTML = matches.map(function (item) {
      var verdict = ["recommended", "possible", "not_recommended", "unknown"].indexOf(item.verdict) >= 0 ? item.verdict : (item.compatibility === true ? "possible" : item.compatibility === false ? "not_recommended" : "unknown");
      var verdictLabels = { recommended: "推荐", possible: "可以考虑", not_recommended: "不建议", unknown: "信息不足" };
      var scoreValue = item.score != null ? Number(item.score) : Number(item.suitabilityScore);
      var score = Number.isFinite(scoreValue) ? Math.max(0, Math.min(1, scoreValue)) : null;
      var concerns = Array.isArray(item.concerns) ? item.concerns : (Array.isArray(item.blockers) ? item.blockers : []);
      var missing = Array.isArray(item.missingInformation) ? item.missingInformation : [];
      var evidence = Array.isArray(item.evidenceRefs) ? item.evidenceRefs : [];
      var legacyReasons = Array.isArray(item.compatibilityReasons) ? item.compatibilityReasons : [];
      var explanation = item.explanation || (verdict === "not_recommended" ? concerns[0] : legacyReasons[0]) || "Agent 未提供额外说明。";
      var detailItems = concerns.concat(missing.map(function (value) { return "未知：" + value; })).concat(evidence.map(function (value) { return "证据：" + value; }));
      var statusClassName = verdict === "recommended" ? "compatible" : verdict === "possible" ? "adaptable" : verdict === "not_recommended" ? "blocked" : "neutral";
      var resultClass = verdict === "not_recommended" ? "incompatible" : verdict === "unknown" ? "unknown" : "compatible";
      return '<article class="discovery-result ' + resultClass + '" data-testid="task-discovery-result-explanation"><div class="discovery-result-head"><div><span class="resource-kind"><i class="resource-type-dot"></i>数据集</span><h3>' + escapeHtml(item.name || item.resourceId) + '</h3></div><div><span class="status-pill ' + statusClassName + '">' + verdictLabels[verdict] + '</span>' + (score == null ? "" : '<strong class="discovery-score">' + Math.round(score * 100) + '</strong>') + '</div></div><p class="discovery-explanation">' + escapeHtml(explanation) + '</p>' + (detailItems.length ? '<ul class="discovery-details">' + detailItems.slice(0, 8).map(function (value) { return "<li>" + escapeHtml(value) + "</li>"; }).join("") + "</ul>" : "") + '<div class="discovery-result-foot"><span>' + escapeHtml(score == null ? "Agent 未给出数值评分" : "Agent 置信评分 " + Math.round(score * 100) + "%") + '</span><button class="text-action" type="button" data-detail-id="' + escapeHtml(item.resourceId) + '" data-detail-kind="dataset">查看详情</button></div></article>';
    }).join("");
    bindDynamicButtons();
  }
  async function runTaskDiscovery() {
    var text = $("taskDiscoveryInput").value.trim();
    if (!text) { showToast("请先描述目标任务"); return; }
    if (state.discovery.running) return;
    state.discovery.running = true;
    $("runTaskDiscovery").disabled = true;
    $("runTaskDiscovery").textContent = "分析中…";
    $("taskDiscoveryStatus").className = "status-pill profiling";
    $("taskDiscoveryStatus").textContent = "Agent 正在理解任务与数据集";
    try {
      var response = await request("/api/dataset-task-matches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });
      renderTaskDiscovery(await response.json());
      $("taskDiscoveryStatus").className = "status-pill compatible";
      $("taskDiscoveryStatus").textContent = "Agent 结论已更新";
    } catch (error) {
      $("taskDiscoveryStatus").className = "status-pill failed";
      $("taskDiscoveryStatus").textContent = "分析失败";
      showToast("任务匹配失败：" + error.message);
    } finally {
      state.discovery.running = false;
      $("runTaskDiscovery").disabled = false;
      $("runTaskDiscovery").innerHTML = '查找数据集 <span>→</span>';
    }
  }

  function clearTrace() {
    state.trace = [];
    $("compatTimeline").innerHTML = '<div class="empty-state compact"><span class="empty-symbol">○</span><p>等待服务端事件</p></div>';
    $("traceCount").textContent = "未开始";
    setAgentActivity("idle", "等待开始", "选择资源后，智能体会在这里汇报当前阶段。");
  }
  function stageId(event) {
    var raw = String(event.stage || event.phase || event.name || event.message || "").toLowerCase();
    var aliases = { discovering: "discover", downloading: "acquire", scanning: "scan", profiling: "profile", deterministic: "compare", llm: "recommend", result: "complete", validate: "discover", prepare: "acquire", agent: "recommend", candidate: "recommend" };
    if (aliases[event.stage]) return aliases[event.stage];
    if (stageNames[event.stage]) return event.stage;
    if (/发现|识别|discover/.test(raw)) return "discover"; if (/拉取|下载|acquir|download/.test(raw)) return "acquire";
    if (/扫描|scan/.test(raw)) return "scan"; if (/描述|profile/.test(raw)) return "profile";
    if (/证据|evidence/.test(raw)) return "evidence"; if (/比对|兼容|compar/.test(raw)) return "compare";
    if (/转换|建议|recommend|transform/.test(raw)) return "recommend"; if (/校验|验证|verify/.test(raw)) return "verify";
    if (/完成|complete|success/.test(raw)) return "complete"; return null;
  }
  function setAgentActivity(status, title, detail) {
    var activity = $("agentActivity");
    if (!activity) return;
    activity.className = "agent-activity " + status;
    $("agentActivityTitle").textContent = title;
    $("agentActivityDetail").textContent = detail;
  }
  function traceDetail(event, id, status) {
    if (status === "running") return traceStageMessages[id] || "智能体正在处理当前阶段";
    if (status === "error") return "当前阶段未完成，请检查分析报告中的错误信息";
    if (status === "skipped") return "该阶段已跳过，继续使用已有分析结果";
    if (id === "complete") return traceStageMessages.complete;
    return "已完成" + (traceStageNames[id] ? "：" + traceStageNames[id] : "");
  }
  function friendlyTraceNote(event) {
    var message = String(event && (event.message || event.detail || "") || "");
    if (!message) return "";
    if (/大语言模型|LLM|字段语义|语义分析/i.test(message)) return "正在等待语义分析结果";
    if (/确定性|契约检查|兼容性检查/i.test(message)) return "正在复核确定性检查结果";
    if (/报告|结构化结果/i.test(message)) return "正在整理结构化分析结论";
    return "";
  }
  function handleTrace(event) {
    if (typeof event === "string") event = { message: event };
    if (!event) return;
    state.trace.push(event);
    var id = stageId(event);
    var note = friendlyTraceNote(event);
    if (!id) {
      if (note) {
        var activeItem = $("compatTimeline").querySelector(".timeline-event.running:last-child");
        if (activeItem) activeItem.querySelector(".timeline-detail").textContent = note;
        $("agentActivityDetail").textContent = note;
      }
      return;
    }
    var timeline = $("compatTimeline"), existing = timeline.querySelector('[data-stage="' + id + '"]');
    var status = event.status === "started" ? "running" : ["error", "failed"].indexOf(event.status) >= 0 ? "error" : event.status === "skipped" ? "skipped" : ["completed"].indexOf(event.status) >= 0 || event.done ? "done" : "running";
    var detail = traceDetail(event, id, status);
    var rawMessage = event.message || event.detail || event.content || event.name || "";
    if (existing) {
      existing.className = "timeline-event " + status;
      existing.querySelector(".timeline-detail").textContent = detail;
      existing.querySelector(".timeline-time").textContent = formatTime();
      var raw = existing.querySelector(".timeline-raw");
      if (raw && rawMessage) raw.textContent = rawMessage;
    } else {
      var emptyTimeline = timeline.querySelector(".empty-state"); if (emptyTimeline) emptyTimeline.remove();
      var item = document.createElement("div"); item.className = "timeline-event " + status; item.dataset.stage = id;
      item.innerHTML = '<div class="timeline-node-wrap"><span class="timeline-node"></span></div><div class="timeline-copy"><p class="timeline-title">' + escapeHtml(traceStageNames[id] || "处理阶段") + '</p><p class="timeline-detail">' + escapeHtml(detail) + '</p>' + (rawMessage ? '<details class="timeline-details"><summary>查看详情</summary><p class="timeline-raw">' + escapeHtml(rawMessage) + "</p></details>" : "") + '</div><span class="timeline-time">' + formatTime() + "</span>";
      timeline.appendChild(item);
    }
    $("traceCount").textContent = status === "error" ? "分析失败" : id === "complete" && status === "done" ? "已完成" : "进行中";
    var activityStatus = status === "running" ? "running" : status === "error" ? "error" : id === "complete" && status === "done" ? "done" : "settled";
    var activityTitle = status === "running" ? "正在" + (traceStageNames[id] || "处理当前阶段") : status === "error" ? "分析未完成" : id === "complete" ? traceStageMessages.complete : "已完成：" + (traceStageNames[id] || "当前阶段");
    setAgentActivity(activityStatus, activityTitle, status === "running" ? (note || traceStageMessages[id] || detail) : status === "error" ? (event.message || "当前阶段出现问题，请查看详情") : detail);
  }

  function renderReport(report) {
    var target = $("reportContent");
    if (!report) {
      state.report = null; state.reportContext = null;
      target.className = "report-empty"; target.innerHTML = '<span class="report-glyph">◌</span><p>选择一组已就绪资源开始分析。</p>'; $("reportStatus").className = "status-pill neutral"; $("reportStatus").textContent = "尚未分析"; return;
    }
    state.report = report;
    var status = report.status || "unknown", dimensions = report.dimensions || [], mappings = report.fieldMappings || report.field_mappings || [], transforms = report.transforms || report.recommendations || [], blockers = report.blockers || [];
    target.className = "report-body";
    $("reportStatus").className = "status-pill " + (status === "compatible" ? "compatible" : status === "adaptable" ? "adaptable" : status === "blocked" ? "blocked" : "neutral");
    $("reportStatus").textContent = { compatible: "可直接使用", adaptable: "转换后可用", blocked: "存在阻断", unknown: "信息不足" }[status] || "待确认";
    var dimensionHtml = dimensions.length ? dimensions.map(function (dimension) {
      var dStatus = dimension.status === "blocked" ? "blocked" : ["warning", "incompatible", "unknown"].indexOf(dimension.status) >= 0 ? "warning" : "";
      return '<div class="dimension-item"><i class="dimension-dot ' + dStatus + '"></i><span class="dimension-name">' + escapeHtml(dimensionNames[dimension.name] || dimension.name || "未命名维度") + '</span><span class="dimension-reason">' + escapeHtml(dimension.reason || "暂无说明") + "</span></div>";
    }).join("") : '<p class="detail-description">服务未返回维度明细。</p>';
    var transformHtml = transforms.length ? '<div class="report-section-title"><span>转换建议</span><small>' + transforms.length + " 条</small></div><ul class=\"recommendation-list\">" + transforms.map(function (item) {
      return "<li>" + escapeHtml(typeof item === "string" ? item : item.description || item.name || JSON.stringify(item)) + "</li>";
    }).join("") + "</ul>" : "";
    var mappingHtml = mappings.length ? '<div class="report-section-title"><span>字段映射</span><small>' + mappings.length + " 条</small></div><ul class=\"mapping-list\">" + mappings.map(function (item) {
      var kind = { exact: "确定", semantic: "语义", transform: "转换" }[item.kind] || item.kind || "建议";
      var confidence = Number.isFinite(Number(item.confidence)) ? Math.round(Number(item.confidence) * 100) + "%" : "—";
      return '<li><div><strong>' + escapeHtml(item.datasetField || "未命名字段") + " → " + escapeHtml(item.modelField || "未命名输入") + '</strong><small>' + escapeHtml(kind + "映射 · 置信度 " + confidence) + "</small></div><p>" + escapeHtml(item.reason || "暂无说明") + "</p></li>";
    }).join("") + "</ul>" : "";
    var blockerHtml = blockers.length ? '<div class="report-section-title"><span>阻断项</span><small>需要处理</small></div><ul class="blocker-list">' + blockers.map(function (item) {
      return "<li>" + escapeHtml(typeof item === "string" ? item : item.message || item.reason || JSON.stringify(item)) + "</li>";
    }).join("") + "</ul>" : "";
    var transformAction = status === "adaptable"
      ? '<div class="transform-action"><div><strong>已找到可执行的字段映射</strong><span>生成新的数据集后，原始数据集仍会保留。</span></div><button id="startTransform" class="primary-button" type="button">生成适配数据集 <span>→</span></button></div>'
      : "";
    target.innerHTML = '<div class="report-summary"><strong class="score">' + (Number.isFinite(Number(report.score)) ? Math.round(Number(report.score) * 100) + "分" : "—") + '</strong><div><p>' + escapeHtml(report.summary || "兼容性分析已完成，请查看下方证据与建议。") + "</p></div></div>" +
      transformAction + '<div class="report-section-title"><span>兼容性维度</span><small>' + dimensions.length + " 项</small></div><div class=\"dimension-list\">" + dimensionHtml + "</div>" + mappingHtml + transformHtml + blockerHtml;
    if (status === "adaptable") {
      $("startTransform").onclick = function () { startDatasetTransform(); };
    }
  }

  function setTransformState(status, title, description) {
    var stateElement = $("transformState");
    stateElement.className = "transform-state " + status;
    $("transformStatus").textContent = title;
    $("transformDescription").textContent = description;
    $("transformRetry").hidden = ["failed", "completed"].indexOf(status) < 0;
    $("transformRetry").textContent = status === "completed" ? "用于匹配" : "重新生成";
    $("transformClose").textContent = status === "running" ? "后台运行" : "关闭";
  }
  function resetTransformProgress() {
    $("transformProgressBar").style.width = "0%";
    $("transformProgress").textContent = "准备中";
    $("transformEventList").innerHTML = "";
    $("transformEventCount").textContent = "0 条";
  }
  function addTransformEvent(message) {
    if (!message) return;
    var target = $("transformEventList");
    var item = document.createElement("div");
    item.className = "import-event";
    item.textContent = message;
    target.appendChild(item);
    target.scrollTop = target.scrollHeight;
    $("transformEventCount").textContent = target.children.length + " 条";
  }
  function applyTransformProgress(event) {
    var message = event.message || event.label || event.detail || (event.name && stageNames[event.name]) || (event.stage && stageNames[event.stage]);
    if (message) addTransformEvent(message);
    var progress = Number(event.percent || event.progress || event.percentage);
    if (Number.isFinite(progress)) {
      progress = progress <= 1 ? progress * 100 : progress;
      progress = Math.max(0, Math.min(100, progress));
      $("transformProgressBar").style.width = progress + "%";
      $("transformProgress").textContent = Math.round(progress) + "%";
    } else if (event.name || event.stage) {
      $("transformProgress").textContent = stageNames[event.name || event.stage] || "处理中";
    }
  }
  function openTransformDrawer(dataset, model) {
    $("transformDatasetName").textContent = dataset.name || dataset.source || "数据集";
    $("transformModelName").textContent = model.name || model.source || "模型";
    resetTransformProgress();
    setTransformState("running", "正在闭环适配数据集", "智能体会生成受约束计划、处理文件、重新解析，并用标准兼容性分析复检；只有复检通过才会加入管理。");
    openDrawer("transformDrawer");
  }
  function finishTransform(resource) {
    var index = state.resources.dataset.findIndex(function (item) { return item.id === resource.id; });
    if (index >= 0) state.resources.dataset[index] = resource; else state.resources.dataset.unshift(resource);
    state.transform.resource = resource;
    state.transform.status = "completed";
    $("transformProgressBar").style.width = "100%";
    $("transformProgress").textContent = "已完成";
    addTransformEvent("适配数据集已生成、重新解析并通过兼容性复检");
    setTransformState("completed", "适配数据集已验证", "新的数据集已通过再次兼容性分析，可以继续匹配。");
    renderResourceGrid("dataset");
    populateResourceSelects();
    showToast("适配数据集已加入管理");
  }
  async function startDatasetTransform(context) {
    if (state.transform.running) {
      showToast("转换正在进行，请等待当前任务完成");
      return;
    }
    context = context || state.reportContext;
    var dataset = context && state.resources.dataset.find(function (item) { return item.id === context.datasetId; });
    var model = context && state.resources.model.find(function (item) { return item.id === context.modelId; });
    var report = context && context.report;
    if (!dataset || !model || !report || report.status !== "adaptable") {
      showToast("请先完成一份可转换的兼容性分析");
      return;
    }
    state.transform.running = true;
    state.transform.context = context;
    state.transform.resource = null;
    state.transform.status = "running";
    openTransformDrawer(dataset, model);
    addTransformEvent("开始创建适配数据集");
    try {
      var response = await request("/api/dataset-transform", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream, application/json" },
        body: JSON.stringify({
          datasetResourceId: dataset.id,
          modelResourceId: model.id,
          report: report
        })
      });
      var result = null, failure = null;
      await consumeSse(response, {
        data: function (data) {
          result = data.resource ? data : data.result || data;
          applyTransformProgress(data);
        },
        event: function (event) {
          if (event.eventName === "result" || event.resource || event.result) {
            result = event.resource ? event : event.result || event;
          } else if (event.eventName === "error" || event.error) {
            failure = event.message || event.error;
          } else if (event.eventName !== "end") {
            applyTransformProgress(event);
          }
        }
      });
      if (failure) throw new Error(typeof failure === "string" ? failure : failure.message || "数据集转换失败");
      var payload = result && (result.resource || result);
      if (!payload || !payload.id) throw new Error("服务结束时没有返回新的数据集");
      var resource = normalizeResource(Object.assign({}, payload, { profile: result.profile || payload.profile }), "dataset");
      finishTransform(resource);
    } catch (error) {
      state.transform.status = "failed";
      addTransformEvent("转换失败：" + error.message);
      setTransformState("failed", "生成失败", error.message || "转换任务未能完成，请重试。");
      $("transformProgress").textContent = "失败";
      showToast("适配数据集生成失败：" + error.message);
    } finally {
      state.transform.running = false;
    }
  }
  function useTransformedDataset() {
    var resource = state.transform.resource;
    if (!resource) return;
    closeDrawers();
    switchView("match");
    populateResourceSelects();
    $("datasetSelect").value = resource.id;
    if (state.transform.context && state.transform.context.modelId) {
      $("modelSelect").value = state.transform.context.modelId;
      updateSelectMeta("model");
    }
    updateSelectMeta("dataset");
    showToast("已选用适配数据集");
  }
  function handleTransformAction() {
    if (state.transform.status === "completed") useTransformedDataset();
    else if (state.transform.status === "failed") startDatasetTransform(state.transform.context);
  }
  async function runCompatibility() {
    if (state.running) return;
    var dataset = selected("dataset"), model = selected("model");
    if (!dataset || !model) { showToast("请选择一个已就绪数据集和模型"); return; }
    state.running = true; clearTrace(); renderReport(null); $("runCompatibility").disabled = true; $("runCompatibility").innerHTML = "分析中…"; $("matchStatus").className = "status-pill running"; $("matchStatus").textContent = "正在分析";
    try {
      var response = await request("/api/compatibility", { method: "POST", headers: { "Content-Type": "application/json", Accept: "text/event-stream, application/json" }, body: JSON.stringify({ datasetResourceId: dataset.id, modelResourceId: model.id, timeoutMs: Number($("timeoutSetting").value || 90000) }) });
      var result = null, failure = null;
      await consumeSse(response, { data: function (data) { result = data.result || data.report || data; }, event: function (event) {
        if (event.eventName === "result" || event.report || event.result || ["compatible", "adaptable", "blocked"].indexOf(event.status) >= 0) result = event.result || event.report || event;
        else if (event.eventName === "error" || event.error) failure = event.message || event.error;
        else if (event.eventName === "end") return;
        else handleTrace(event);
      } });
      if (failure) throw new Error(typeof failure === "string" ? failure : failure.message || "兼容性分析失败");
      renderReport(result); state.reportContext = result ? { datasetId: dataset.id, modelId: model.id, report: result } : null; handleTrace({ stage: "complete", status: "completed", message: "兼容性报告已生成" });
      var reportStatus = result && result.status; $("matchStatus").className = "status-pill " + (reportStatus === "blocked" ? "blocked" : reportStatus === "adaptable" ? "adaptable" : reportStatus === "compatible" ? "compatible" : "neutral"); $("matchStatus").textContent = reportStatus === "blocked" ? "存在阻断" : reportStatus === "adaptable" ? "转换后可用" : reportStatus === "compatible" ? "可直接使用" : "信息不足"; showToast("兼容性分析完成");
    } catch (error) { state.reportContext = null; handleTrace({ stage: "verify", status: "error", message: error.message }); $("matchStatus").className = "status-pill blocked"; $("matchStatus").textContent = "分析失败"; showToast("兼容性分析失败：" + error.message); }
    finally { state.running = false; $("runCompatibility").disabled = false; $("runCompatibility").innerHTML = "开始兼容性分析 <span>→</span>"; }
  }

  async function loadConfig() {
    try {
      var response = await request("/api/config-status"), config = await response.json();
      var configured = config.configured !== false && config.hasApiKey !== false && config.apiKeyConfigured !== false;
      $("configState").textContent = configured ? "已配置" : "未配置"; $("configModel").textContent = config.model || config.llmModel || "glm-5.3-flash"; $("configEndpoint").textContent = config.endpoint ? config.endpoint.replace(/^https?:\/\//, "").slice(0, 44) : "已隐藏"; setService(configured ? "服务已连接" : "需要配置", configured ? "ready" : "warn");
    } catch (error) { $("configState").textContent = "未连接"; $("configModel").textContent = "glm-5.3-flash"; $("configEndpoint").textContent = "等待服务端"; setService("服务未连接", "warn"); }
  }
  async function loadWorkspace() {
    try {
      var response = await request("/api/workspace");
      var workspace = await response.json();
      state.workspace = workspace;
      $("workspacePathInput").value = workspace.resourceStorePath || "";
      $("workspaceDatasetPath").textContent = workspace.datasetPath || "—";
      $("workspaceModelPath").textContent = workspace.modelPath || "—";
      $("workspaceState").className = "status-pill " + (workspace.exists ? "ready" : "neutral");
      $("workspaceState").textContent = workspace.exists ? "已连接" : "尚未创建";
      $("workspacePathWarning").textContent = workspace.exists
        ? "切换路径只会改变读取位置，不会复制或移动已有数据。新路径为空时，两类资源都会显示为空。"
        : "当前目录尚未创建，首次导入资源时会在这里建立目录；不会从旧工作区复制内容。";
    } catch (error) {
      $("workspaceState").className = "status-pill blocked";
      $("workspaceState").textContent = "读取失败";
      $("workspacePathWarning").textContent = "工作区状态读取失败：" + error.message;
    }
  }
  async function saveWorkspace() {
    var input = $("workspacePathInput");
    var nextPath = input.value.trim();
    var currentPath = state.workspace.resourceStorePath || "";
    if (!nextPath) { showToast("请填写资源工作区路径"); return; }
    if (nextPath === currentPath) { showToast("资源工作区未发生变化"); return; }
    var confirmed = window.confirm(
      "确定切换资源工作区？\n\n" +
      "系统只会切换读取路径，不会自动复制或移动数据集、算法代码库和已有描述。\n" +
      "如果目标路径为空，数据集和算法库也会显示为空。\n\n" +
      "新路径：\n" + nextPath,
    );
    if (!confirmed) return;
    $("saveWorkspacePath").disabled = true;
    $("workspaceState").className = "status-pill running";
    $("workspaceState").textContent = "切换中";
    try {
      var response = await request("/api/workspace", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resourceStorePath: nextPath })
      });
      state.workspace = await response.json();
      $("workspacePathInput").value = state.workspace.resourceStorePath || nextPath;
      $("workspaceDatasetPath").textContent = state.workspace.datasetPath || "—";
      $("workspaceModelPath").textContent = state.workspace.modelPath || "—";
      $("workspaceState").className = "status-pill " + (state.workspace.exists ? "ready" : "neutral");
      $("workspaceState").textContent = state.workspace.exists ? "已连接" : "尚未创建";
      $("workspacePathWarning").textContent = state.workspace.exists
        ? "切换路径只会改变读取位置，不会复制或移动已有数据。新路径为空时，两类资源都会显示为空。"
        : "当前目录尚未创建，首次导入资源时会在这里建立目录；不会从旧工作区复制内容。";
      state.report = null;
      state.reportContext = null;
      clearTrace();
      renderReport(null);
      $("matchStatus").className = "status-pill neutral";
      $("matchStatus").textContent = "等待选择资源";
      await Promise.all([loadResources("dataset"), loadResources("model")]);
      showToast(state.workspace.exists ? "资源工作区已切换" : "已切换到空的资源工作区");
    } catch (error) {
      $("workspaceState").className = "status-pill blocked";
      $("workspaceState").textContent = "切换失败";
      showToast("资源工作区切换失败：" + error.message);
    } finally {
      $("saveWorkspacePath").disabled = false;
    }
  }
  async function deleteSelectedResource() {
    if (!state.selectedResource) return;
    if (!window.confirm("确定删除这个资源及其本地描述吗？")) return;
    try {
      await request("/api/resources/" + encodeURIComponent(state.selectedResource.id), { method: "DELETE" });
      var kind = state.selectedResource.kind; state.resources[kind] = state.resources[kind].filter(function (item) { return item.id !== state.selectedResource.id; }); closeDrawers(); renderResourceGrid(kind); populateResourceSelects(); showToast("资源已删除");
    } catch (error) { showToast("删除失败：" + error.message); }
  }
  function bind() {
    all("[data-view]").forEach(function (button) { button.onclick = function () { switchView(button.dataset.view); }; });
    all("[data-view-target]").forEach(function (button) { button.onclick = function () { switchView(button.dataset.viewTarget); }; });
    $("refreshDatasets").onclick = function () { loadResources("dataset"); }; $("refreshModels").onclick = function () { loadResources("model"); };
    $("openSettings").onclick = function () { openDrawer("settingsDrawer"); loadConfig(); loadWorkspace(); }; $("saveWorkspacePath").onclick = saveWorkspace; $("searchSource").onclick = searchSource; $("importResource").onclick = importResource; $("deleteResource").onclick = deleteSelectedResource; $("runCompatibility").onclick = runCompatibility; $("runTaskDiscovery").onclick = runTaskDiscovery; $("transformRetry").onclick = handleTransformAction;
    $("sourceTypeSelect").onchange = syncSourceFields; $("chooseLocalFolder").onclick = function () { $("localFolderInput").click(); }; $("localFolderInput").onchange = updateLocalFolderSummary;
    $("datasetSelect").onchange = function () { updateSelectMeta("dataset"); }; $("modelSelect").onchange = function () { updateSelectMeta("model"); };
    all("[data-drawer-kind]").forEach(function (button) { button.onclick = function () { state.drawerKind = button.dataset.drawerKind; all("[data-drawer-kind]").forEach(function (item) { item.classList.toggle("active", item === button); }); $("resourceDrawerTitle").textContent = "添加" + labels[state.drawerKind].title; resetLocalFolderSelection(); configureSourceType(state.drawerKind); }; });
    all("[data-close]").forEach(function (button) { button.onclick = closeDrawers; }); $("backdrop").onclick = closeDrawers; document.addEventListener("keydown", function (event) { if (event.key === "Escape") closeDrawers(); });
  }
  bind(); configureSourceType("dataset"); renderResourceGrid("dataset"); renderResourceGrid("model"); populateResourceSelects(); loadResources("dataset"); loadResources("model"); loadConfig(); loadWorkspace();
})();
