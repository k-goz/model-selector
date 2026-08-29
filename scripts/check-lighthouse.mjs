import fs from 'node:fs';

const report = JSON.parse(fs.readFileSync('output/lighthouse.json', 'utf8'));
const minimums = {performance: 0.75, accessibility: 0.95, 'best-practices': 0.90, seo: 0.90};
const failures = [];
for (const [name, minimum] of Object.entries(minimums)) {
  const score = report.categories[name]?.score ?? 0;
  console.log(`${name}: ${Math.round(score * 100)} (minimum ${Math.round(minimum * 100)})`);
  if (score < minimum) failures.push(`${name}=${score}`);
}
const budget = report.audits['performance-budget'];
if (budget && budget.score !== null && budget.score < 1) failures.push('performance-budget');
if (failures.length) {
  console.error(`Lighthouse gate failed: ${failures.join(', ')}`);
  process.exit(1);
}
