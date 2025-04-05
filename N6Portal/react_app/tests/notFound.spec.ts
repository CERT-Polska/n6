import { expect, Page, test } from '@playwright/test';
import { expectToBeVisibleAndEnabled } from './utils/tools';
import { MockedApi } from './utils/mockedApi';
import { userWithInsideResource } from './utils/mockedUsers';

const triggerPageNotFound = async (page: Page) => {
  await page.goto('/notexistingurl');
  await page.waitForURL('/page-not-found');
};

test('Display `Page not found`', async ({ page }) => {
  await triggerPageNotFound(page);
  expect(page.url()).toEqual('https://localhost/page-not-found');
  await expect(page.getByText('Page not found')).toBeVisible();
  await expect(page.getByText('This page does not exist or')).toBeVisible();
  await expect(page.getByTestId('n6Logo')).toBeVisible();
  await expect(page.getByTestId('notFoundIcon')).toBeVisible();
});

test.describe('`Back to home page` button behaviour', () => {
  test('authenticated user', async ({ page }) => {
    await MockedApi.getUserInfo(page, userWithInsideResource);
    await triggerPageNotFound(page);

    const button = page.getByTestId('notFound_btn');

    await expectToBeVisibleAndEnabled(button);

    await button.click();
    await page.waitForURL('/organization');
    await MockedApi.getUserInfo(page, userWithInsideResource);

    expect(page.url()).toEqual('https://localhost/organization');
    await expect(page.getByTestId('navOrganization')).toBeVisible();
  });

  test('not authenticated user', async ({ page }) => {
    await triggerPageNotFound(page);
    const button = page.getByTestId('notFound_btn');

    await expectToBeVisibleAndEnabled(button);

    await button.click();
    await page.waitForURL('/no-access');

    expect(page.url()).toEqual('https://localhost/no-access');
    await expect(page.getByText('We are sorry')).toBeVisible();
    await expect(page.getByTestId('noAccessIcon')).toBeVisible();
  });
});
