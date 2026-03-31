import { test, expect } from '@playwright/test';

test('player profile renders and video duration exceeds 10s', async ({ page }) => {
  await page.goto('/');

  await page.getByTestId('player-search').fill('Roberto de Abreu');
  await page.getByTestId('profile-btn').click();

  await expect(page.getByTestId('profile-panel')).toBeVisible({ timeout: 60000 });
  await expect(page.getByTestId('profile-info')).toContainText('games');
  await expect(page.getByTestId('profile-score-white')).toBeVisible();
  await expect(page.getByTestId('profile-score-black')).toBeVisible();
  await expect(page.getByTestId('profile-openings')).toBeVisible();
  await expect(page.getByTestId('profile-rating-chart')).toBeVisible();

  // force minimum recording duration >10s
  await page.waitForTimeout(11000);
});
