import { expect, Page, test } from '@playwright/test';
import { generateMockedBinaryListOfIncidentsForMonth, generateDays } from './utils/tools';
import { MockedApi } from './utils/mockedApi';
import { listOfUsers, MockedUser } from './utils/mockedUsers';
import { TestRunner } from './utils/TestRunner';

function execOrganizationTests(user: MockedUser) {
  test.beforeEach(async ({ page }) => {
    await page.getByTestId('navOrganization').click();
    await page.waitForTimeout(1000);
    expect(page.url()).toEqual('https://localhost/organization');
    await expect(page.getByTestId('organization-header-title')).toBeVisible();
  });

  test(`${user.name}: appearance of Organization header`, async ({ page }) => {
    const orgHeaderTitle = page.getByTestId('organization-header-name');

    await expect(orgHeaderTitle).toBeVisible();
    await expect(orgHeaderTitle).toContainText('CERT Polska');
    await expect(page.getByTestId('organization-header-update-icon')).toBeVisible();

    const orgHeaderLastUpdate = page.getByTestId('organization-header-last-update');
    await expect(orgHeaderLastUpdate).toBeVisible();
    await expect(orgHeaderLastUpdate).toContainText('Last update');

    const orgHeaderLastUpdateDate = page.getByTestId('organization-header-last-update-date');
    await expect(orgHeaderLastUpdateDate).toBeVisible();
    await expect(orgHeaderLastUpdateDate).toContainText('17.02.2025, 08:41');

    await expect(page.getByTestId('organization-header-data-range-icon')).toBeVisible();

    const orgHeaderDataRange = page.getByTestId('organization-header-data-range');
    await expect(orgHeaderDataRange).toBeVisible();
    await expect(orgHeaderDataRange).toContainText('Data range');

    const orgHeaderDataRangeValue = page.getByTestId('organization-header-data-range-value');
    await expect(orgHeaderDataRangeValue).toBeVisible();
    await expect(orgHeaderDataRangeValue).toContainText('Last 30 days');
  });

  test(`${user.name}: appearance of Organization chart`, async ({ page }) => {
    await expect(page.getByTestId('organization-chart')).toBeVisible();
    await expect(page.getByTestId('organization-chart-bar')).toBeVisible();
  });

  test(`${user.name}: appearance of Organization chart when data has empty dataset`, async ({ page }) => {
    await MockedApi.mockApiRoute(page, '/api/daily_events_counts', {
      empty_dataset: true
    });
    await page.reload();

    await expect(page.getByTestId('organization-chart-no-data')).toBeVisible();
  });

  test(`${user.name}: appearance of Organization cards`, async ({ page }) => {
    const cards = [
      { id: 'cnc', expectedValue: '1' },
      { id: 'bots', expectedValue: '1' },
      { id: 'vulnerable', expectedValue: '1' },
      { id: 'amplifier', expectedValue: '1' },
      { id: 'malurl', expectedValue: '1' },
      { id: 'all', expectedValue: '5' }
    ];

    await expect(page.getByTestId('organization-cards-container')).toBeVisible();

    for (const card of cards) {
      await expect(page.getByTestId(`organization-card-${card.id}`)).toBeVisible();
      await expect(page.getByTestId(`organization-card-title-${card.id}`)).toBeVisible();
      await expect(page.getByTestId(`organization-card-tooltip-${card.id}`)).toBeVisible();
      await expect(page.getByTestId(`organization-card-value-${card.id}`)).toBeVisible();
      await expect(page.getByTestId(`organization-card-value-${card.id}`)).toContainText(card.expectedValue);
    }
  });

  test(`${user.name}: appearance of Organization table events`, async ({ page }) => {
    async function checkOrganizationTableEvents(page: Page, category: string) {
      await expect(page.getByTestId(`organization-table-events-header-${category}`)).toBeVisible();
      await expect(page.getByTestId(`organization-table-event-header-number-${category}`)).toBeVisible();
      await expect(page.getByTestId(`organization-table-event-header-name-${category}`)).toBeVisible();
      await expect(page.getByTestId(`organization-table-event-header-events-count-${category}`)).toBeVisible();

      const eventCount = 10;
      for (let i = 1; i <= eventCount; i++) {
        await expect(page.getByTestId(`organization-table-event-number-${category}-${i}`)).toBeVisible();
        await expect(page.getByTestId(`organization-table-event-name-${category}-${i}`)).toBeVisible();

        if (i === 1) {
          await expect(page.getByTestId(`organization-table-event-name-${category}-${i}`)).toContainText('virut');
          await expect(page.getByTestId(`organization-table-event-count-${category}-${i}`)).toContainText('2');
        } else if (i <= 6) {
          await expect(page.getByTestId(`organization-table-event-name-${category}-${i}`)).toContainText('testName');
          await expect(page.getByTestId(`organization-table-event-count-${category}-${i}`)).toContainText('1');
        } else {
          await expect(page.getByTestId(`organization-table-event-name-${category}-${i}`)).toContainText('-');
          await expect(page.getByTestId(`organization-table-event-count-${category}-${i}`)).toContainText('-');
        }
      }
    }

    await checkOrganizationTableEvents(page, 'bots');
    await checkOrganizationTableEvents(page, 'amplifier');
    await checkOrganizationTableEvents(page, 'vulnerable');
  });
}

const runner = TestRunner.builder
  .withTestName('Organization Tests')
  .withUsers(listOfUsers)
  .withBeforeEach(async (page, user) => {
    await MockedApi.getUserInfo(page, user);
    await MockedApi.mockApiRoute(page, '/api/dashboard', {
      at: '2025-02-17T08:41:29Z',
      time_range_in_days: 30,
      counts: {
        cnc: 1,
        bots: 1,
        vulnerable: 1,
        amplifier: 1,
        malurl: 1,
        all: 5
      }
    });
    await MockedApi.mockApiRoute(page, '/api/names_ranking', {
      bots: {
        '1': {
          virut: 2
        },
        '2': { testName: 1 },
        '3': { testName: 1 },
        '4': { testName: 1 },
        '5': { testName: 1 },
        '6': { testName: 1 },
        '7': null,
        '8': null,
        '9': null,
        '10': null
      },
      amplifier: {
        '1': {
          virut: 2
        },
        '2': { testName: 1 },
        '3': { testName: 1 },
        '4': { testName: 1 },
        '5': { testName: 1 },
        '6': { testName: 1 },
        '7': null,
        '8': null,
        '9': null,
        '10': null
      },
      vulnerable: {
        '1': {
          virut: 2
        },
        '2': { testName: 1 },
        '3': { testName: 1 },
        '4': { testName: 1 },
        '5': { testName: 1 },
        '6': { testName: 1 },
        '7': null,
        '8': null,
        '9': null,
        '10': null
      }
    });
    await MockedApi.mockApiRoute(page, '/api/daily_events_counts', {
      days: generateDays(2025, 1),
      datasets: {
        bots: generateMockedBinaryListOfIncidentsForMonth(2025, 1),
        cnc: generateMockedBinaryListOfIncidentsForMonth(2025, 1),
        'server-exploit': [],
        scanning: [],
        spam: []
      }
    });
    await page.goto('/');
    await MockedApi.getUserInfo(page, user);
  })
  .withTests((user) => {
    if (user.availableResources.includes('/report/inside')) {
      execOrganizationTests(user);
    } else {
      test(`${user.name}: lack appearance of Organization nav tab`, async ({ page }) => {
        await expect(page.getByTestId('navOrganization')).not.toBeVisible();
      });
    }
  })
  .build();

runner.runTests();
