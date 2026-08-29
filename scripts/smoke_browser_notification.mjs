import { chromium } from '@playwright/test';

const target = new URL(process.argv[2] || 'http://127.0.0.1:4173/');
const browser = await chromium.launch({ headless: false });

try {
  const context = await browser.newContext();
  await context.grantPermissions(['notifications'], { origin: target.origin });
  const page = await context.newPage();
  await page.goto(target.href, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.catalogModels?.length > 0 && window.ModelSelectorAlerts);
  await page.evaluate(() => window.ModelSelectorAlerts.open());
  await page.locator('#alertTest').click();
  await page.waitForFunction(() => ['sent', 'failed'].includes(window.ModelSelectorAlerts.deliveries()[0]?.status));
  const result = await page.evaluate(() => ({
    permission: Notification.permission,
    serviceWorker: 'serviceWorker' in navigator,
    delivery: window.ModelSelectorAlerts.deliveries()[0],
  }));
  if (result.delivery?.status !== 'sent') throw new Error(`notification delivery failed: ${result.delivery?.reason || 'unknown'}`);
  console.log(JSON.stringify({ target: target.origin, permission: result.permission, serviceWorker: result.serviceWorker, status: result.delivery.status, channel: result.delivery.channel }));
  await page.waitForTimeout(1000);
} finally {
  await browser.close();
}
