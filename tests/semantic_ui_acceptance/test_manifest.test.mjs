import { describe, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";

const manifestUrl = new URL(
  "../../docs/semantic-ui-acceptance/dom-fixture-manifest.json",
  import.meta.url
);
const manifest = JSON.parse(await Bun.file(manifestUrl).text());
const indexHtml = await readFile(new URL("../../web/index.html", import.meta.url), "utf8");
const appJs = await readFile(new URL("../../web/app.js", import.meta.url), "utf8");

const selectorPattern = /^\[data-testid="(?:semantic|task-discovery)-[a-z0-9]+(?:-[a-z0-9]+)*"\]$/;
const selectorIdPattern = /^(?:semantic|task-discovery)-[a-z0-9]+(?:-[a-z0-9]+)*$/;
const requiredTopLevelKeys = [
  "schemaVersion",
  "automation",
  "viewports",
  "visualRegression",
  "fixtureContract",
  "selectors",
  "reviewRegions",
  "workflowRequirements",
  "accessibilityRules",
  "layoutRules",
  "sseReconnectChecks",
  "fixtures",
  "requiredCoverage"
];

function ids(items) {
  return items.map((item) => item.id);
}

function expectUnique(values, description) {
  expect(new Set(values).size).toBe(values.length);
  expect(values.every(Boolean)).toBe(true);
}

describe("semantic UI acceptance manifest", () => {
  test("has the frozen Phase 0 contract structure", () => {
    expect(manifest.schemaVersion).toBe(1);
    for (const key of requiredTopLevelKeys) {
      expect(manifest).toHaveProperty(key);
    }
    expect(manifest.automation.phase0Validator.command).toBe(
      "bun test tests/semantic_ui_acceptance/test_manifest.test.mjs"
    );
    expect(manifest.automation.phase0Validator.requiresNetwork).toBe(false);
    expect(manifest.automation.phase0Validator.requiresRealApi).toBe(false);
    expect(manifest.contractStatus).toBe("phase-0-frozen-2026-09-09");
    expect(manifest.automation.phase7BrowserHarness.status).toBe(
      "required-not-installed-at-phase-0"
    );
  });

  test("defines the exact desktop and mobile viewports and visual archive policy", () => {
    expect(manifest.viewports).toEqual([
      {
        id: "desktop-1440x1100",
        width: 1440,
        height: 1100,
        deviceScaleFactor: 1,
        isMobile: false
      },
      {
        id: "mobile-390x844",
        width: 390,
        height: 844,
        deviceScaleFactor: 2,
        isMobile: true
      }
    ]);
    expect(manifest.visualRegression.baselineRoot).toBe(
      "tests/semantic_ui_acceptance/baselines"
    );
    expect(manifest.visualRegression.failureArchiveRoot).toBe(
      ".datamodelmatch/ui-acceptance"
    );
    expect(manifest.visualRegression.comparison.maximumMismatchedPixelRatio).toBe(
      0.002
    );
    expect(manifest.visualRegression.comparison.maximumMismatchedPixels).toBe(800);
  });

  test("uses unique, stable data-testid selectors with semantic workflow coverage", () => {
    const selectorIds = ids(manifest.selectors);
    expectUnique(selectorIds, "selector IDs");

    for (const item of manifest.selectors) {
      expect(item.id).toMatch(selectorIdPattern);
      expect(item.selector).toMatch(selectorPattern);
      expect(["semantic-profile-details-review", "task-driven-dataset-discovery"]).toContain(
        item.workflow
      );
      expect(item.purpose.length).toBeGreaterThan(8);
    }

    const requiredSelectorIds = [
      "semantic-details-root",
      "semantic-details-profile-status",
      "semantic-details-structure-region",
      "semantic-details-content-region",
      "semantic-details-evidence-region",
      "semantic-details-job-progress",
      "task-discovery-root",
      "task-discovery-query-input",
      "task-discovery-task-profile",
      "task-discovery-resource-scope",
      "task-discovery-compatibility-filter",
      "task-discovery-sort-explanation",
      "task-discovery-ranked-results",
      "task-discovery-nonranked-results",
      "task-discovery-result-explanation",
      "task-discovery-job-progress"
    ];
    for (const selectorId of requiredSelectorIds) {
      expect(selectorIds).toContain(selectorId);
    }
  });

  test("freezes exactly three completed details review regions", () => {
    expect(manifest.reviewRegions).toHaveLength(3);
    expect(manifest.reviewRegions.map((item) => item.id)).toEqual(
      manifest.requiredCoverage.reviewRegionIds
    );
    const selectorIds = new Set(ids(manifest.selectors));
    for (const region of manifest.reviewRegions) {
      expect(selectorIds.has(region.selectorId)).toBe(true);
      expect(region.heading.length).toBeGreaterThan(1);
      expect(region.mustShow.length).toBeGreaterThanOrEqual(5);
    }
  });

  test("covers both workspaces, all required fixtures, and valid fixture selector references", () => {
    const workflowIds = Object.keys(manifest.workflowRequirements);
    expect(workflowIds.sort()).toEqual([...manifest.requiredCoverage.workflowIds].sort());

    const declaredStates = new Set(manifest.fixtureContract.states);
    const fixtureStates = new Set(manifest.fixtures.map((fixture) => fixture.state));
    for (const state of manifest.requiredCoverage.fixtureStates) {
      expect(declaredStates.has(state)).toBe(true);
      expect(fixtureStates.has(state)).toBe(true);
    }

    const selectorIds = new Set(ids(manifest.selectors));
    expectUnique(ids(manifest.fixtures), "fixture IDs");
    for (const fixture of manifest.fixtures) {
      expect(manifest.requiredCoverage.workflowIds).toContain(fixture.workflow);
      expect(declaredStates.has(fixture.state)).toBe(true);
      expect(fixture.requiredSelectorIds.length).toBeGreaterThan(0);
      for (const selectorId of fixture.requiredSelectorIds) {
        expect(selectorIds.has(selectorId)).toBe(true);
      }
    }
  });

  test("contains complete keyboard, layout, and SSE reconnect rules", () => {
    expect(ids(manifest.accessibilityRules)).toEqual(
      manifest.requiredCoverage.accessibilityRuleIds
    );
    expect(ids(manifest.layoutRules)).toEqual(manifest.requiredCoverage.layoutRuleIds);
    for (const rule of [...manifest.accessibilityRules, ...manifest.layoutRules]) {
      expect(rule.rule.length).toBeGreaterThan(30);
    }

    expect(manifest.sseReconnectChecks).toHaveLength(2);
    for (const check of manifest.sseReconnectChecks) {
      expect(manifest.requiredCoverage.workflowIds).toContain(check.workflow);
      expect(manifest.fixtures.map((fixture) => fixture.id)).toContain(check.fixture);
      expect(check.assertions.length).toBeGreaterThanOrEqual(4);
    }
  });

  test("keeps task discovery inside dataset management and describes Agent-led semantic matching", () => {
    expect(indexHtml).toContain('id="view-datasets"');
    expect(indexHtml).toContain('data-testid="task-discovery-root"');
    expect(indexHtml).toContain('data-testid="task-discovery-query-input"');
    expect(indexHtml).toContain("Agent 会结合数据集证据理解需求并给出推荐理由");
    expect(indexHtml).not.toContain("先验证结构兼容性，再按内容适配度排序");
    expect(indexHtml).not.toContain("结构兼容优先");
  });

  test("supports Agent verdict payloads with legacy matching fallbacks and escaped rendering", () => {
    for (const key of ["verdict", "score", "explanation", "concerns", "evidenceRefs", "missingInformation"]) {
      expect(appJs).toContain("item." + key);
    }
    expect(appJs).toContain("item.compatibility");
    expect(appJs).toContain("item.suitabilityScore");
    expect(appJs).toContain("escapeHtml(explanation)");
    expect(appJs).toContain("Agent 置信评分");
    expect(appJs).toContain("未知：");
  });

  test("puts completed semantic analysis before raw dataset fields in details", () => {
    expect(appJs).toContain('data-testid="semantic-details-root"');
    expect(appJs).toContain("Agent 语义分析");
    expect(appJs).toContain("可支持的任务");
    expect(appJs).toContain("证据与待确认事项");
    expect(appJs).not.toContain("Agent 执行与图片采样");
    expect(appJs).not.toContain("semantic-details-agent-execution-region");
    expect(appJs).not.toContain("没有可用于视觉观察的样本，Agent 仅使用结构和文档证据。");
    expect(appJs).toContain("原始字段与结构");
    expect(appJs.indexOf("semanticProfileSection(resource.semanticProfile, resource.id)")).toBeLessThan(
      appJs.indexOf("原始字段与结构")
    );
  });

  test("updates semantic progress in place without resetting message-list scrolling", () => {
    expect(appJs).toContain("data-semantic-progress-messages");
    expect(appJs).toContain("messages.scrollTop = messages.scrollHeight");
    expect(appJs).not.toContain("outerHTML = semanticProgressMarkup");
  });

  test("shows stream-backed task-discovery progress without forcing the message list to scroll", () => {
    expect(indexHtml).toContain('data-testid="task-discovery-job-progress"');
    expect(appJs).toContain("startTaskDiscoveryProgress()");
    expect(appJs).toContain("renderTaskDiscoveryProgress(event)");
    expect(appJs).toContain("Agent 正在依据任务目标、数据集能力、局限和已记录证据，对所有候选集进行排序。");
    expect(appJs).toContain('Accept: "text/event-stream, application/json"');
    expect(appJs).toContain("if (atBottom) messages.scrollTop = messages.scrollHeight");
  });
});
