const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const modelData = JSON.parse(fs.readFileSync(path.join(__dirname, '../../models_data.json'), 'utf8'));

async function waitForCatalog(page) {
  await page.goto('/');
  await expect(page.locator('#grid .mc')).toHaveCount(modelData.models.length);
  await expect(page.locator('#filterCount strong')).toHaveText(String(modelData.models.length));
}

async function openSidebar(page) {
  const toggle = page.locator('.sidebar-toggle');
  if (await toggle.isVisible()) {
    await toggle.click();
  }
  await expect(page.locator('#sidebar')).toBeVisible();
}

async function expandSidebarGroup(page, name) {
  const title = page.locator('.fg-title', { hasText: name });
  const group = title.locator('..');
  if (await group.evaluate(element => element.classList.contains('fg-collapsed'))) {
    await title.click();
  }
  await expect(group.locator('.fg-body')).toBeVisible();
}

function collectBrowserErrors(page) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('response', response => {
    if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`);
  });
  return errors;
}

test('loads the complete catalog without browser errors', async ({ page }) => {
  const errors = collectBrowserErrors(page);
  await waitForCatalog(page);
  await expect(page).toHaveTitle(/AI 模型选择器/);
  expect(errors).toEqual([]);
});

test('search and platform filters update visible model count', async ({ page }) => {
  await waitForCatalog(page);
  await openSidebar(page);
  await page.locator('#si').fill('deepseek-v4-pro');
  const searchCount = Number(await page.locator('#filterCount strong').textContent());
  expect(searchCount).toBeGreaterThan(0);
  expect(searchCount).toBeLessThan(modelData.models.length);

  await page.getByRole('button', { name: '✕ 清除筛选' }).click();
  await expandSidebarGroup(page, '算力供应商');
  await page.locator('.pt[data-p="openrouter"]').click();
  const openRouterCount = Number(await page.locator('#filterCount strong').textContent());
  expect(openRouterCount).toBe(modelData.meta.platform_counts.openrouter);
});

test('currency, layout, theme and compare interactions remain functional', async ({ page }) => {
  await waitForCatalog(page);
  await openSidebar(page);
  await expandSidebarGroup(page, '工具');
  await page.locator('.cur-btn[data-cur="USD"]').click();
  await expect(page.locator('.cur-btn[data-cur="USD"]')).toHaveClass(/active/);

  await page.locator('#listBtn').click();
  await expect(page.locator('#grid')).toHaveClass(/list-view/);

  await page.locator('button[onclick="toggleDark()"]', { hasText: '亮色' }).click();
  await expect(page.locator('body')).toHaveClass(/light/);

  const checkboxes = page.locator('#grid .mc:visible .mc-cb');
  await checkboxes.nth(0).check();
  await checkboxes.nth(1).check();
  await expect(page.locator('#cmpCount')).toHaveText('2');
  await expect(page.locator('#cmpPanel')).toBeVisible();
});

test('English page loads the same catalog', async ({ page }) => {
  const errors = collectBrowserErrors(page);
  await page.goto('/en/');
  await expect(page.locator('#grid .mc')).toHaveCount(modelData.models.length);
  await expect(page).toHaveTitle(/AI Model Selector/);
  expect(errors).toEqual([]);
});

test('filter state survives a page reload', async ({ page }) => {
  await waitForCatalog(page);
  await openSidebar(page);
  await page.locator('#si').fill('deepseek-v4-pro');
  await expect.poll(() => page.url()).toContain('#');
  const filteredCount = await page.locator('#filterCount strong').textContent();

  await page.reload();
  await expect(page.locator('#grid .mc')).toHaveCount(modelData.models.length);
  await expect(page.locator('#si')).toHaveValue('deepseek-v4-pro');
  await expect(page.locator('#filterCount strong')).toHaveText(filteredCount);
});

test('token calculator produces ranked estimates', async ({ page }) => {
  await waitForCatalog(page);
  await openSidebar(page);
  await expandSidebarGroup(page, '工具');
  await page.getByRole('button', { name: /计价/ }).click();
  await expect(page.locator('#tkModal')).toHaveClass(/show/);
  await page.locator('#tkText').fill('请估算这段中文和 English code: console.log("hello")');
  await page.getByRole('button', { name: '计算 Token' }).click();
  await expect(page.locator('#tkStats .tk-stat')).toHaveCount(4);
  await expect(page.locator('#tkResult .tk-result-table tr')).not.toHaveCount(1);
});

test('model card opens switchable and copyable integration code', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await waitForCatalog(page);
  const firstCard = page.locator('#grid .mc:visible').first();
  const modelName = (await firstCard.locator('.mname').textContent()).trim();
  await firstCard.locator('.mname').click();
  await expect(page.locator('#codeModal')).toHaveClass(/show/);
  await expect(page.locator('#codeModal .cm-model')).toHaveText(modelName);
  await page.locator('.code-tab[data-lang="curl"]').click();
  await expect(page.locator('#codeBlock pre')).toContainText('curl ');
  await page.locator('.code-copy-btn').click();
  await expect(page.locator('.code-copy-btn')).toHaveText('已复制');
});
