import { Page, test, expect } from '@playwright/test';
import { expectToBeVisibleAndEnabled } from './utils/tools';
import { MockedApi } from './utils/mockedApi';
import { availableResources, listOfUsers, MockedUser } from './utils/mockedUsers';
import { TestRunner } from './utils/TestRunner';

const checkLink = async (page: Page, goToUrl = '', testId: string, waitForUrl: string) => {
  if (goToUrl !== '') {
    await page.goto(goToUrl);
  }
  const link = page.getByTestId(testId);
  await expectToBeVisibleAndEnabled(link);
  await link.click();
  await page.waitForURL(waitForUrl);

  expect(page.url()).toEqual(`https://localhost${waitForUrl}`);
};

function executeHeaderTests(user: MockedUser) {
  test('Logo N6 Portal should redirect to home (incidents) page', async ({ page }) => {
    await checkLink(page, '/organization', 'n6Logo', '/incidents');
  });

  test.describe('Tabs', () => {
    if (user.availableResources.includes(availableResources.inside)) {
      test('`Your organization` tab should redirect to /organization page', async ({ page }) => {
        await checkLink(page, '/incidents', 'navOrganization', '/organization');
      });
    } else {
      test('`Your organization` tab should not be visible', async ({ page }) => {
        await expect(page.getByTestId('navOrganization')).not.toBeVisible();
      });
    }

    test('`All incidents` tab should redirect to /incidents page', async ({ page }) => {
      await checkLink(page, '/organization', 'navIncidents', '/incidents');
    });

    if (user.knowledgeBaseEnabled) {
      test('`Knowledge base` tab should redirect to /knowledge_base page', async ({ page }) => {
        await checkLink(page, '/incidents', 'navKnowledgeBase', '/knowledge_base');
      });
    } else {
      test('`Knowledge base` tab should not be visible', async ({ page }) => {
        await expect(page.getByTestId('navKnowledgeBase')).not.toBeVisible();
      });
    }
  });

  test.describe('User menu', () => {
    test.beforeEach(async ({ page }) => {
      await page.goto('/incidents');
      await page.getByTestId('userMenuNavBtn').click();
    });

    test('Account information', async ({ page }) => {
      await checkLink(page, undefined, 'userMenuNavAccount', '/account');
    });

    test('User settings', async ({ page }) => {
      await checkLink(page, undefined, 'userMenuNavUserSettings', '/user-settings');
    });

    test('Organization settings', async ({ page }) => {
      await checkLink(page, undefined, 'userMenuNavOrgSettings', '/settings');
    });

    test('(EN | PL) Language selection, should change page translation', async ({ page }) => {
      const enBtn = page.getByTestId('languagePickerEN');
      const plBtn = page.getByTestId('languagePickerPL');
      await expectToBeVisibleAndEnabled(enBtn);
      await expectToBeVisibleAndEnabled(plBtn);

      await plBtn.click();
      await expect(page.getByTestId('navIncidents')).toContainText('Incydenty');

      await page.getByTestId('userMenuNavBtn').click();
      await enBtn.click();
      await expect(page.getByTestId('navIncidents')).toContainText('All incidents');
    });

    test('Logout', async ({ page }) => {
      const link = page.getByTestId('userMenuNavLogout');

      await expectToBeVisibleAndEnabled(link);

      await MockedApi.getLogout(page);
      await MockedApi.getNotAuthenticatedUserInfo(page);
      await link.click();
      await page.waitForURL('/');

      await expect(page.getByText("Don't have an account?")).toBeVisible();
      expect(page.url()).toEqual(`https://localhost/`);
    });
  });
}

const runner = TestRunner.builder
  .withTestName('Header Tests')
  .withUsers(listOfUsers)
  .withBeforeEach(async (page, user) => {
    await MockedApi.getUserInfo(page, user);
  })
  .withTests((user) => {
    executeHeaderTests(user);
  })
  .build();

runner.runTests();
