import { test, expect } from '@playwright/test';

async function runSingleGame(page: any, gameIndex: number) {
  await page.goto('/');

  await page.getByTestId('player-search').fill('Roberto de Abreu');
  await page.getByTestId('search-btn').click();

  const loadButtons = page.locator('button[data-testid^="load-"]');
  await expect(loadButtons.first()).toBeVisible({ timeout: 60000 });

  const total = await loadButtons.count();
  expect(total).toBeGreaterThan(gameIndex);

  await loadButtons.nth(gameIndex).click();
  await expect(page.getByTestId('loaded-game-id')).toBeVisible();

  const firstTxt = await page.getByTestId('move-progress').textContent();
  const first = firstTxt?.match(/Move\s+(\d+)\/(\d+)/);
  expect(first).not.toBeNull();
  const totalMoves = Number(first![2]);
  expect(totalMoves).toBeGreaterThan(0);

  await page.getByTestId('slow-play').click();

  await expect.poll(async () => {
    const txt = await page.getByTestId('move-progress').textContent();
    const m = txt?.match(/Move\s+(\d+)\/(\d+)/);
    if (!m) return false;
    return Number(m[1]) === Number(m[2]);
  }, { timeout: 300000 }).toBe(true);
}

for (let i = 0; i < 10; i++) {
  test(`player search Roberto de Abreu and slow-play game #${i + 1}`, async ({ page }) => {
    await runSingleGame(page, i);
  });
}
