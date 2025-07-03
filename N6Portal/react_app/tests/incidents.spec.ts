import * as fs from 'fs';
import { test, expect, Page, Locator } from '@playwright/test';
import { format, subDays } from 'date-fns';
import { expectToBeVisibleAndEnabled, expectHeaderIsVisibleAndEnabled, fillInput } from './utils/tools';
import { MockedApi, mockedEvents } from './utils/mockedApi';
import { dictionary } from '../src/dictionary';
import { MockedUser, availableResources, listOfUsers } from './utils/mockedUsers';
import { TestRunner } from './utils/TestRunner';

const columnsFilterTestIds = [
  {
    checkboxTestId: 'ASN-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'Category-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'Client-column-filter-checkbox',
    isChecked: false,
    isVisibleForUser: async (user: MockedUser) => {
      return user.fullAccess;
    }
  },
  {
    checkboxTestId: 'Confidence-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'Country-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'Destination IP-column-filter-checkbox',
    isChecked: false
  },
  {
    checkboxTestId: 'FQDN-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'IP-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'Protocol-column-filter-checkbox',
    isChecked: false
  },
  {
    checkboxTestId: 'Restriction-column-filter-checkbox',
    isChecked: false
  },
  {
    checkboxTestId: 'SHA1-column-filter-checkbox',
    isChecked: false
  },
  {
    checkboxTestId: 'Source-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'Time (UTC)-column-filter-checkbox',
    isChecked: true
  },
  {
    checkboxTestId: 'URL-column-filter-checkbox',
    isChecked: true
  }
];

export const IncidentFilters = [
  'asn',
  'category',
  'client',
  'cc',
  'dport',
  'fqdn',
  'fqdnSub',
  'endDate',
  'ip',
  'ipNet',
  'md5',
  'name',
  'nameSub',
  'proto',
  'restriction',
  'sha1',
  'source',
  'sport',
  'target',
  'url',
  'urlSub',
  'id'
];

function execIncidentsTests(user: MockedUser) {
  test(`${user.name} should display incidents page elements`, async ({ page }) => {
    expect(page.url()).toEqual('https://localhost/incidents');
    await expectHeaderIsVisibleAndEnabled(page, user);
    await expect(page.getByText('Choose search criteria')).toBeVisible();
  });

  test.describe('Columns', () => {
    test(`${user.name} Columns dropdown button`, async ({ page }) => {
      await expectToBeVisibleAndEnabled(page.getByTestId('columns-filter-dropdown-btn'));
    });

    test(`${user.name} Columns filter buttons`, async ({ page }) => {
      const checkCheckboxAndLabel = async (
        page: Page,
        testId: string,
        isCheckedByDefault: boolean,
        isVisibleForUser: Function = () => true
      ) => {
        const checkboxInput = page.getByTestId(testId);
        const checkboxBtn = page.getByTestId(`${testId}-btn`);
        const visibleForUser = await isVisibleForUser(user);

        if (visibleForUser) {
          await expect(page.getByTestId(`${testId}-label`)).toBeVisible();
          await expectToBeVisibleAndEnabled(checkboxBtn);

          if (isCheckedByDefault) {
            await expect(checkboxInput).toBeChecked();
            await checkboxBtn.click();
            await expect(checkboxInput).not.toBeChecked();
            await checkboxBtn.click();
            await expect(checkboxInput).toBeChecked();
          } else {
            await expect(checkboxInput).not.toBeChecked();
            await checkboxBtn.click();
            await expect(checkboxInput).toBeChecked();
            await checkboxBtn.click();
            await expect(checkboxInput).not.toBeChecked();
          }
        } else {
          await expect(page.getByTestId(`${testId}-label`)).not.toBeVisible();
        }
      };

      const checkColumnsFilterItems = async (page: Page) => {
        for (const checkbox of columnsFilterTestIds) {
          await checkCheckboxAndLabel(page, checkbox.checkboxTestId, checkbox.isChecked, checkbox.isVisibleForUser);
        }
      };

      await MockedApi.getIncidentEvent(page, user.availableResources[0]);
      await fillInput(page, 'date-picker-input-startDate', '01122000');
      await expect(page.getByTestId('date-picker-input-startDate')).toHaveValue('01-12-2000');
      await page.getByTestId('incidents-search-submit-btn').click();

      await page.getByTestId('columns-filter-dropdown-btn').click();
      await checkColumnsFilterItems(page);
    });
  });

  test.describe('Datepicker', () => {
    test.describe('Date input', () => {
      test(`${user.name} is visible and enabled`, async ({ page }) => {
        await expectToBeVisibleAndEnabled(page.getByTestId('date-picker-input-startDate'));
      });

      test(`${user.name} is filled with default value`, async ({ page }) => {
        const input = page.getByTestId('date-picker-input-startDate');
        const date = subDays(new Date(), 7);
        const formattedDate = format(date, 'dd-MM-yyyy');

        await expect(input).toHaveValue(formattedDate);
      });

      test(`${user.name} can be filled with a new valid date`, async ({ page }) => {
        const input = await fillInput(page, 'date-picker-input-startDate', '01012012');
        await expect(input).toHaveValue('01-01-2012');
      });

      test(`${user.name} can not be filled with a non valid date`, async ({ page }) => {
        const date = subDays(new Date(), 7);
        const formattedDate = format(date, 'dd-MM-yyyy');

        const input = await fillInput(page, 'date-picker-input-startDate', 'nonValidDate');
        await expect(input).not.toHaveValue('nonValidDate');

        await input.fill('22222222');
        await input.blur();
        await expect(input).toHaveValue(formattedDate);
      });
    });

    test.describe('Calendar', () => {
      const clickCalendarIcon = async (page: Page) => {
        await page.getByTestId('date-picker-calendar-icon-btn').click();
      };

      const checkDateBtns = async (array: string[] | number[], isItMonth: boolean, page: Page) => {
        for (const element of array) {
          const elementBtn = page.getByTestId(`calendar-${isItMonth ? 'month' : 'year'}-menu-${element}-btn`);
          await expectToBeVisibleAndEnabled(elementBtn);
        }
      };

      const expectMonthsBtnsToBeVisibleAndEnabled = async (page: Page) => {
        const months = Array.from({ length: 12 }, (_, index) =>
          new Date(0, index).toLocaleString('default', { month: 'long' })
        );

        await checkDateBtns(months, true, page);
      };

      const expectYearBtnsToBeVisibleAndEnabled = async (page: Page) => {
        const getYears = () => {
          const currentYear = new Date().getFullYear();
          return Array.from({ length: currentYear - 2000 + 1 }, (_, index) => 2000 + index);
        };

        await checkDateBtns(getYears(), false, page);
      };

      test(`${user.name} Calendar icon button opens up the calendar tooltip`, async ({ page }) => {
        const calendarBtn = page.getByTestId('date-picker-calendar-icon-btn');
        await expectToBeVisibleAndEnabled(calendarBtn);

        await calendarBtn.click();
        await expect(page.getByTestId('data-picker-calendar')).toBeVisible();
      });

      test(`${user.name} Calendar has the default date marked correctly`, async ({ page }) => {
        await clickCalendarIcon(page);

        const currentDate = subDays(new Date(), 7);
        const currentDay = currentDate.getDate();
        const currentMonth = currentDate.toLocaleString('default', { month: 'long' });
        const currentYear = currentDate.getFullYear();

        await expect(page.getByTestId('calendar-month-selected')).toHaveText(currentMonth);
        await expect(page.getByTestId('calendar-year-selected')).toHaveText(currentYear.toString());
        await expect(page.getByTestId('calendar-day-selected')).toHaveText(currentDay.toString());
      });

      test(`${user.name} Select '12 February 2020' date via clicking on rendered calendar tooltip`, async ({
        page
      }) => {
        await clickCalendarIcon(page);

        const selectedMonthBtn = page.getByTestId('calendar-month-dropdown-btn');
        const selectedYearBtn = page.getByTestId('calendar-year-dropdown-btn');

        await expectToBeVisibleAndEnabled(selectedMonthBtn);
        await expectToBeVisibleAndEnabled(selectedYearBtn);

        await selectedMonthBtn.click();
        await expectMonthsBtnsToBeVisibleAndEnabled(page);
        await page.getByTestId('calendar-month-menu-February-btn').click();
        await expect(page.getByTestId('calendar-month-selected')).toHaveText('February');

        await selectedYearBtn.click();
        await expectYearBtnsToBeVisibleAndEnabled(page);
        await page.getByTestId('calendar-year-menu-2020-btn').click();
        await expect(page.getByTestId('calendar-year-selected')).toHaveText('2020');

        await page.getByTestId('calendar-day-12-btn').click();
        await expect(page.getByTestId('data-picker-calendar')).not.toBeVisible();
        await clickCalendarIcon(page);
        await expect(page.getByTestId('calendar-day-selected')).toHaveText('12');

        await expect(page.getByTestId('date-picker-input-startDate')).toHaveValue('12-02-2020');
      });
    });
  });

  test.describe('Incidents startTime input', () => {
    test(`${user.name} is enabled and visible`, async ({ page }) => {
      await expectToBeVisibleAndEnabled(page.getByTestId('incidents-startTime'));
    });

    test(`${user.name} can not be filled with characters`, async ({ page }) => {
      const input = await fillInput(page, 'incidents-startTime', 'randomString');
      await expect(input).not.toHaveValue('randomString');
    });

    test(`${user.name} is filled with default value`, async ({ page }) => {
      await expect(page.getByTestId('incidents-startTime')).toHaveValue('00:00');
    });

    test(`${user.name} can be filled with valid value`, async ({ page }) => {
      const input = await fillInput(page, 'incidents-startTime', '1245', { blur: true });

      await expect(input).toHaveValue('12:45');
    });
  });

  test.describe('Export', () => {
    test(`${user.name} Export dropdown button`, async ({ page }) => {
      await expectToBeVisibleAndEnabled(page.getByTestId('export-dropdown-btn'));
    });

    test.describe('Disabled links', async () => {
      const expectToHaveDisabledClsAndBeVisible = async (element: Locator) => {
        await expect(element).toHaveClass(/disabled/);
        await expect(element).toBeVisible();
      };

      test.beforeEach(async ({ page }) => {
        await page.getByTestId('export-dropdown-btn').click();
      });

      test(`${user.name} CSV link`, async ({ page }) => {
        const csvLink = page.getByTestId('export-csv-link-disabled');
        await expectToHaveDisabledClsAndBeVisible(csvLink);
      });

      test(`${user.name} JSON link`, async ({ page }) => {
        const jsonLink = page.getByTestId('export-json-link-disabled');
        await expectToHaveDisabledClsAndBeVisible(jsonLink);
      });
    });

    test.describe('Enabled links', async () => {
      const expectDownloadedFile = async (page: Page, link: Locator, expectedContent: string | object) => {
        const [download] = await Promise.all([page.waitForEvent('download'), await link.click()]);

        const downloadPath = await download.path();
        expect(downloadPath).not.toBeNull();

        expect(fs.existsSync(downloadPath)).toBe(true);

        const fileContent = fs.readFileSync(downloadPath, 'utf-8');
        expect(fileContent).toContain(expectedContent);

        try {
          fs.unlinkSync(downloadPath);
          console.log(`File deleted: ${downloadPath}`);
        } catch (err) {
          console.error(`Failed to delete the file: ${downloadPath}`, err);
        }
      };

      const expectedCsvContent = `"ID","Time (UTC)","Category","Source","IP","ASN","Country","FQDN","Confidence","URL","Restriction","Protocol","Src.port","Dest.port","Destination IP","SHA1","Anonymized Destination IP","Client"
"a3a3384e2707a865c24a3ab3803f9f97","2015-06-05T22:22:33Z","cnc","source.channel","1.1.1.1 2.2.2.2","1000 ","TT TT","testdomain.com","medium","http://testdomain.com/internal","internal","tcp","1000","1000","3.3.3.3","a3a3782bfc7aa9c8f0ad63e5e54a5bdc04a49a5d","x.x.x.82","client.com"`;

      const expectedJsonContent = `[
  {
    "source": "source.channel",
    "confidence": "medium",
    "modified": "2016-07-05T22:22:33Z",
    "sport": 1000,
    "address": [
      {
        "cc": "TT",
        "ip": "1.1.1.1",
        "asn": 1000
      },
      {
        "cc": "TT",
        "ip": "2.2.2.2"
      }
    ],
    "proto": "tcp",
    "rid": "5678b8dde1b9c2d362684e942dd4ea01",
    "adip": "x.x.x.82",
    "fqdn": "testdomain.com",
    "category": "cnc",
    "sha1": "a3a3782bfc7aa9c8f0ad63e5e54a5bdc04a49a5d",
    "time": "2015-06-05T22:22:33Z",
    "ignored": false,
    "client": [
      "client.com"
    ],
    "dip": "3.3.3.3",
    "dport": 1000,
    "url": "http://testdomain.com/internal",
    "id": "a3a3384e2707a865c24a3ab3803f9f97",
    "restriction": "internal"
  }
]`;

      test.beforeEach(async ({ page }) => {
        await MockedApi.getIncidentEvent(page, user.availableResources[0]);
        await fillInput(page, 'date-picker-input-startDate', '01122000');
        await expect(page.getByTestId('date-picker-input-startDate')).toHaveValue('01-12-2000');
        await page.getByTestId('incidents-search-submit-btn').click();
        await page.getByTestId('export-dropdown-btn').click();
      });

      test(`${user.name} download CSV file`, async ({ page }) => {
        const csvLink = page.getByTestId('export-csv-link');

        await expectToBeVisibleAndEnabled(csvLink);
        await expectDownloadedFile(page, csvLink, expectedCsvContent);
      });

      test(`${user.name} download JSON file`, async ({ page }) => {
        const jsonLink = page.getByTestId('export-json-link');

        await expectToBeVisibleAndEnabled(jsonLink);
        await expectDownloadedFile(page, jsonLink, expectedJsonContent);
      });
    });
  });

  test.describe('Search button', () => {
    const expectCorrectRequestURL = async (page: Page, url: string, addAndFillFilter?: () => Promise<void>) => {
      await fillInput(page, 'date-picker-input-startDate', '01012000');
      await fillInput(page, 'incidents-startTime', '1200');

      if (addAndFillFilter) {
        await addAndFillFilter();
      }

      const requestPromise = page.waitForRequest(url);
      await page.getByTestId('incidents-search-submit-btn').click();
      const request = await requestPromise;

      expect(request.url()).toEqual(url);
    };

    test(`${user.name} with no additional filters sends start date, time and limit in url request`, async ({
      page
    }) => {
      const url = MockedApi.buildIncidentSearchUrl(user.availableResources[0], {
        dateTime: new Date(Date.UTC(2000, 0, 1, 12, 0, 0))
      });
      await expectCorrectRequestURL(page, url);
    });

    test(`${user.name} with additional ASN filter sends request with asn query parameter`, async ({ page }) => {
      const url = MockedApi.buildIncidentSearchUrl(user.availableResources[0], {
        dateTime: new Date(Date.UTC(2000, 0, 1, 12, 0, 0)),
        filterQuery: 'asn=123&'
      });

      await expectCorrectRequestURL(page, url, async () => {
        await page.getByTestId('incidents-add-filter-btn').click();
        await page.getByTestId('asn_filter_item').click();
        await page.getByTestId('incidents-filter-asn-input').fill('123');
      });
    });

    test(`${user.name} search event and display a table`, async ({ page }) => {
      await MockedApi.getIncidentEvent(page, user.availableResources[0]);

      await fillInput(page, 'date-picker-input-startDate', '01122000');
      await page.getByTestId('incidents-search-submit-btn').click();

      await expect(page.getByTestId('incidents-table')).toBeVisible();
    });
  });

  test.describe('Add filter', () => {
    test(`${user.name} Add filter button`, async ({ page }) => {
      const addFilterBtn = page.getByTestId('incidents-add-filter-btn');
      await expectToBeVisibleAndEnabled(addFilterBtn);
      await addFilterBtn.click();
      await expectToBeVisibleAndEnabled(page.getByTestId('asn_filter_item'));
    });

    test(`${user.name} each filter button is visible, enabled, editable and add filter input`, async ({ page }) => {
      for (const filter of IncidentFilters) {
        await page.getByTestId('incidents-add-filter-btn').click();
        const selectedTabContent = await page.getByTestId('/report/inside_tab_parent').first().allTextContents();
        const isInsideTab = selectedTabContent.includes(dictionary['en']['account_resources_/report/inside']);

        if (!user.fullAccess) {
          await expect(page.getByTestId('restriction_filter_item')).not.toBeVisible();
          await expect(page.getByTestId('client_filter_item')).not.toBeVisible();
          await expect(page.getByTestId('nameSub_filter_item')).not.toBeVisible();
          continue;
        }
        if (isInsideTab && filter === 'client') {
          await expect(page.getByTestId('client_filter_item')).not.toBeVisible();
          await page.getByTestId('incidents-add-filter-btn').click();
          continue;
        }

        const filterBtn = page.getByTestId(`${filter}_filter_item`);
        await expectToBeVisibleAndEnabled(filterBtn);
        await filterBtn.click();

        if (filter === 'endDate') {
          const filterInput = page.getByTestId(`date-picker-input-endDate`);
          await expectToBeVisibleAndEnabled(filterInput, async () => {
            await expect(filterInput).toBeEditable();
          });
        } else {
          const filterInput = page.getByTestId(`incidents-filter-${filter}-input`);
          await expectToBeVisibleAndEnabled(filterInput, async () => {
            await expect(filterInput).toBeEditable();
          });
        }
      }
    });
  });

  test.describe('Incidents table', () => {
    const defaultOrderedColumnsHeadersWithDescription = {
      0: dictionary.en.incidents_column_header_time,
      1: dictionary.en.incidents_column_header_category,
      2: dictionary.en.incidents_column_header_source,
      3: dictionary.en.incidents_column_header_ip,
      4: dictionary.en.incidents_column_header_asn,
      5: dictionary.en.incidents_column_header_cc,
      6: dictionary.en.incidents_column_header_fqdn
    };

    const mockedEvent = {
      0: '2015-06-05 22:22:33',
      1: 'cnc',
      // 2: 'virut',
      2: 'source.channel',
      3: '1.1.1.1\n2.2.2.2\n',
      4: '1000\n\n',
      5: 'TT\nTT\n',
      6: 'testdomain.com',
      7: 'medium',
      8: 'http://testdomain.com/in...',
      9: 'internal',
      10: 'mocktext'
    };

    const clickAsnAndCategoryColumnsFilter = async (page: Page) => {
      await page.getByTestId('columns-filter-dropdown-btn').click();
      await page.getByTestId('ASN-column-filter-checkbox-btn').click();
      await page.getByTestId('Category-column-filter-checkbox-btn').click();
      await page.click('body');
    };

    const expectColumnToHaveText = async (
      page: Page,
      columnIndex: number,
      expectedText: string,
      options: {
        shouldExist: boolean;
      }
    ) => {
      const columnHeader = page.getByTestId(`incidents-table-columnHeader-${columnIndex}`);
      if (options?.shouldExist) {
        await expect(columnHeader).toHaveText(expectedText);
      } else {
        await expect(columnHeader).not.toHaveText(expectedText);
      }
    };

    const fillAndSubmitSearch = async (page: Page, mockedApiCallback: () => Promise<void>) => {
      await mockedApiCallback();
      await fillInput(page, 'date-picker-input-startDate', '01122000');
      await page.getByTestId('incidents-search-submit-btn').click();
    };

    const expectColumnHeaderNotToExist = async (columnHeaders: Locator, options: { headers: string[] }) => {
      const headerCount = await columnHeaders.count();
      for (let idx = 0; idx < headerCount; idx++) {
        const header = columnHeaders.nth(idx);
        for (const headerText of options.headers) {
          await expect(header).not.toHaveText(headerText);
        }
      }
    };

    test.beforeEach(async ({ page }) => {
      await fillAndSubmitSearch(page, async () => {
        await MockedApi.getIncidentEvent(page, user.availableResources[0]);
      });
    });

    test(`${user.name} Default column headers exists`, async ({ page }) => {
      for (const [index, headerText] of Object.entries(defaultOrderedColumnsHeadersWithDescription)) {
        const header = page.getByTestId(`incidents-table-columnHeader-${index}`);
        await expect(header).toBeVisible();
        await expect(header).toHaveText(headerText);
      }
    });

    test(`${user.name} Hiding columns works via Columns filter buttons`, async ({ page }) => {
      const columnHeaders = page.locator('[data-testid^="incidents-table-columnHeader"]');
      await expect(columnHeaders).toHaveCount(9);
      await clickAsnAndCategoryColumnsFilter(page);

      await expectColumnHeaderNotToExist(columnHeaders, { headers: ['Category', 'ASN'] });
      await expect(columnHeaders).toHaveCount(7);

      await clickAsnAndCategoryColumnsFilter(page);

      await expectColumnToHaveText(page, 1, 'Category', { shouldExist: true });
      await expectColumnToHaveText(page, 4, 'ASN', { shouldExist: true });
    });

    test(`${user.name} Hidden columns are not being displayed after page refresh or another search query`, async ({
      page
    }) => {
      const columnHeaders = page.locator('[data-testid^="incidents-table-columnHeader"]');
      await expect(columnHeaders).toHaveCount(9);

      await clickAsnAndCategoryColumnsFilter(page);
      await page.getByTestId('incidents-search-submit-btn').click();

      await expectColumnHeaderNotToExist(columnHeaders, { headers: ['Category', 'ASN'] });

      await page.reload();
      await page.waitForTimeout(50);
      await fillAndSubmitSearch(page, async () => {
        await MockedApi.getIncidentEvent(page, user.availableResources[0]);
      });

      await expectColumnHeaderNotToExist(columnHeaders, { headers: ['Category', 'ASN'] });
    });

    test(`${user.name} Reset Columns button change table to the dynamic behavior`, async ({ page }) => {
      const columnHeaders = page.locator('[data-testid^="incidents-table-columnHeader"]');
      await expect(columnHeaders).toHaveCount(9);

      await clickAsnAndCategoryColumnsFilter(page);
      await page.getByTestId('incidents-search-submit-btn').click();
      await expect(columnHeaders).toHaveCount(7);
      await expectColumnHeaderNotToExist(columnHeaders, { headers: ['Category', 'ASN'] });

      await page.reload();
      await page.waitForTimeout(50);
      await fillAndSubmitSearch(page, async () => {
        await MockedApi.getIncidentEvent(page, user.availableResources[0]);
      });

      await expect(columnHeaders).toHaveCount(7);

      await page.getByTestId('columns-filter-dropdown-btn').click();
      await page.getByTestId('reset-table-columns-btn').click();

      await expect(columnHeaders).toHaveCount(9);
      await expectColumnToHaveText(page, 1, 'Category', { shouldExist: true });
      await expectColumnToHaveText(page, 4, 'ASN', { shouldExist: true });
    });

    test(`${user.name} Rows with values exists`, async ({ page }) => {
      for (let i = 0; i < Object.keys(defaultOrderedColumnsHeadersWithDescription).length; i++) {
        const cell = page.getByTestId(`incidents-table-row-0-cell-${i}`);
        await expect(cell).toBeVisible();
        const cellText = await cell.innerText();
        expect(cellText).toEqual(mockedEvent[i]);
      }
    });

    test(`${user.name} Sorting rows via column header`, async ({ page }) => {
      await fillAndSubmitSearch(page, async () => {
        await MockedApi.getTwoIncidentEvents(page, user.availableResources[0]);
      });

      await expect(page.getByTestId('incidents-table-columnHeader-Name')).not.toBeVisible();

      const columnHeader = page.getByTestId('incidents-table-columnHeader-0');
      await columnHeader.click();

      const firstRowfirstCell = page.getByTestId('incidents-table-row-0-cell-0');
      const secondRowfirstCell = page.getByTestId('incidents-table-row-1-cell-0');

      await expect(firstRowfirstCell).toHaveText('2015-06-05 22:22:33');
      await expect(secondRowfirstCell).toHaveText('2016-06-05 22:22:33');

      await columnHeader.click();

      await expect(firstRowfirstCell).toHaveText('2016-06-05 22:22:33');
      await expect(secondRowfirstCell).toHaveText('2015-06-05 22:22:33');

      await columnHeader.click();

      await expect(firstRowfirstCell).toHaveText('2015-06-05 22:22:33');
      await expect(secondRowfirstCell).toHaveText('2016-06-05 22:22:33');
    });
  });
}
const goToIncidentsPage = async (page: Page) => {
  await page.goto('/incidents');
  await page.waitForURL('/incidents');
  await page.waitForTimeout(1000);
};

const expectTabsToBeVisible = async (
  page: Page,
  ...visibleTabs: Array<(typeof availableResources)[keyof typeof availableResources]>
) => {
  const allResources = Object.values(availableResources);

  for (const resource of allResources) {
    const tabElement = page.getByTestId(`${resource}_tab`);
    if (visibleTabs.includes(resource)) {
      await expect(tabElement).toBeVisible();
    } else {
      await expect(tabElement).not.toBeVisible();
    }
  }
};

const runner = TestRunner.builder
  .withTestName('Incidents Tests')
  .withUsers(listOfUsers)
  .withBeforeEach(async (page, user) => {
    await MockedApi.getUserInfo(page, user);
    await goToIncidentsPage(page);
    await expectTabsToBeVisible(page, ...user.availableResources);
  })
  .withTests((user) => {
    if (user.availableResources.length > 0) {
      execIncidentsTests(user);
    } else {
      test(`${user.name} No available resources`, async ({ page }) => {
        await expect(page.getByTestId('incidents-table')).not.toBeVisible();
      });
    }
  })
  .build();

runner.runTests();
