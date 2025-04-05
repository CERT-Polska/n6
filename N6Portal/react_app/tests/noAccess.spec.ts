import { expect, test } from '@playwright/test';
import { expectToBeVisibleAndEnabled } from './utils/tools';

test.beforeEach(async ({ page }) => {
  await page.goto('/incidents');
  await page.waitForURL('/no-access');
});

test('Display no-access page', async ({ page }) => {
  expect(page.url()).toEqual('https://localhost/no-access');
  await expect(page.getByText("you don't have access to this page")).toBeVisible();
  await expect(page.getByText('We are sorry')).toBeVisible();
  await expect(page.getByTestId('n6Logo')).toBeVisible();
  await expect(page.getByTestId('noAccessIcon')).toBeVisible();
});

test('Go to login page button works', async ({ page }) => {
  const goToLoginPageBtn = page.getByTestId('noAccess_btn');
  await expectToBeVisibleAndEnabled(goToLoginPageBtn);
  await goToLoginPageBtn.click();
  await page.waitForURL('/');
  expect(page.url()).toEqual('https://localhost/');
  await expect(page.getByText("Don't have an account?")).toBeVisible();
});
