import { MockedApi } from './utils/mockedApi';
import { listOfUsers, MockedUser } from './utils/mockedUsers';
import { TestRunner } from './utils/TestRunner';
import { expectExternalLink, expectTabsToBeVisible, fillInput, goToIncidentsPage } from './utils/tools';
import { test, expect, Page } from '@playwright/test';

const fillAndSubmitSearch = async (page: Page, mockedApiCallback: () => Promise<void>) => {
  await mockedApiCallback();
  await fillInput(page, 'date-picker-input-startDate', '01122000');
  await page.getByTestId('incidents-search-submit-btn').click();
};

function executeNameDetailsTests(user: MockedUser) {
  test.beforeEach(async ({ page }) => {
    await fillAndSubmitSearch(page, async () => {
      await MockedApi.getNameDetailsIncidentEvent(page, user.availableResources[0]);
    });
  });

  test(`${user.name} Name/Details feature`, async ({ page }) => {
    const modal = page.getByTestId('enrichment-modal');
    const lightbulbBtn = page.getByTestId('enrichment-lightbulb-icon-btn');
    const closeBtn = page.getByTestId('enrichment-modal-close-btn');

    // Table cell
    await expect(page.getByTestId('incidents-table-row-0-cell-3')).toContainText('CVE-2025-14847, adb');

    // Modal initially hidden
    await expect(modal).toBeHidden();

    // Open modal
    await expect(lightbulbBtn).toBeVisible();
    await expect(lightbulbBtn).toBeEnabled();
    await lightbulbBtn.click();

    // Modal basics
    await expect(modal).toBeVisible();
    await expect(page.getByTestId('enrichment-modal-title')).toHaveText('Name Details');

    // Headers
    const headers = page.getByTestId('enrichment-modal-about-record-header');
    await expect(headers).toHaveCount(2);
    await expect(headers).toHaveText(['About CVE-2025-14847', 'About adb']);

    // External links
    await expectExternalLink(page, 'moje_cert_pl_link', /moje\.cert\.pl/);
    await expectExternalLink(page, 'enisa_link', /euvd\.enisa\.europa\.eu/);
    await expectExternalLink(page, 'knowledge_base_link', /localhost\/knowledge_base\/articles\/1090#n6kb-adb/);

    // Close modal
    await expect(closeBtn).toBeVisible();
    await expect(closeBtn).toBeEnabled();
    await closeBtn.click();

    await expect(modal).toBeHidden();
  });
}

const runner = TestRunner.builder
  .withTestName('Name/Details Feature Tests')
  .withUsers(listOfUsers)
  .withBeforeEach(async (page, user) => {
    await MockedApi.getUserInfo(page, user);
    await goToIncidentsPage(page);
    await expectTabsToBeVisible(page, ...user.availableResources);
  })
  .withTests((user) => {
    if (user.availableResources.length > 0) {
      executeNameDetailsTests(user);
    } else {
      test(`${user.name} No available resources`, async ({ page }) => {
        await expect(page.getByTestId('incidents-table')).not.toBeVisible();
      });
    }
  })
  .build();

runner.runTests();
