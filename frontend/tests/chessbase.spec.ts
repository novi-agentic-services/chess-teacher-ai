import { test, expect } from '@playwright/test';

test('player search Roberto de Abreu and play through 10 games', async ({ page }) => {
  await page.goto('/');

  await page.getByTestId('player-search').fill('Roberto de Abreu');
  await page.getByTestId('search-btn').click();

  const loadButtons = page.locator('button[data-testid^="load-"]');
  await expect(loadButtons.first()).toBeVisible({ timeout: 60000 });

  const total = await loadButtons.count();
  expect(total).toBeGreaterThan(0);

  const runCount = Math.min(10, total);

  for (let i = 0; i < runCount; i++) {
    await loadButtons.nth(i).click();
    await expect(page.getByTestId('loaded-game-id')).toBeVisible();

    await page.getByTestId('play-to-end').click();
    const txt = await page.getByTestId('move-progress').textContent();
    expect(txt).toMatch(/Move\s+\d+\/\d+/);

    // verify completed playback (left == right)
    const m = txt!.match(/Move\s+(\d+)\/(\d+)/);
    expect(m).not.toBeNull();
    expect(Number(m![1])).toBe(Number(m![2]));
  }
});
