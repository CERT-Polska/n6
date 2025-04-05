import { expect, Locator, Page } from '@playwright/test';
import { availableResources, MockedUser } from './mockedUsers';

export const expectToBeVisibleAndEnabled = async (element: Locator, callback?: () => Promise<void>) => {
  await expect(element).toBeVisible();
  await expect(element).toBeEnabled();

  if (callback) {
    await callback();
  }
};

export const expectHeaderIsVisibleAndEnabled = async (page: Page, user: MockedUser) => {
  await expectToBeVisibleAndEnabled(page.getByTestId('n6Logo'));

  if (user.availableResources.includes(availableResources.inside)) {
    await expectToBeVisibleAndEnabled(page.getByTestId('navOrganization'));
  } else {
    await expect(page.getByTestId('navOrganization')).not.toBeVisible();
  }

  await expectToBeVisibleAndEnabled(page.getByTestId('navIncidents'));

  if (user.knowledgeBaseEnabled) {
    await expectToBeVisibleAndEnabled(page.getByTestId('navKnowledgeBase'));
  } else {
    await expect(page.getByTestId('navKnowledgeBase')).not.toBeVisible();
  }

  await expectToBeVisibleAndEnabled(page.getByTestId('userMenuNavBtn'));
};

export const fillInput = async (page: Page, inputTestId: string, filledText: string, options?: { blur: boolean }) => {
  const input = page.getByTestId(inputTestId);
  await input.fill(filledText);

  if (options?.blur) {
    await input.blur();
  }

  return input;
};

export const verifyInput = async (page: Page, testId: string) => {
  const input = page.getByTestId(testId);
  await expect(input).toHaveText('');
  await expect(input).toHaveValue('');
  await expect(input).toBeVisible();
  await expect(input).toBeEditable();
};

export const MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR =
  'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJqdGkiOiJ1bmlxdWUtaWRlbnRpZmllciIsImlhdCI6MTY4MTEwNDAwMCwiZXhwIjoyNTQ1ODQ4MDAwfQ.T4J0ut_Pfc3oGUOcFWJTkAaixeRcLiFa0fqSVZcOkxM';

export function generateDays(year: number, month: number): string[] {
  if (month < 1 || month > 12) {
    throw new Error('Month must be between 1 and 12.');
  }

  if (isNaN(year) || year < 1) {
    throw new Error('Year must be a positive number.');
  }

  const daysInMonth = new Date(year, month, 0).getDate();

  return Array.from({ length: daysInMonth }, (_, day) => {
    const formattedMonth = month.toString().padStart(2, '0');
    const formattedDay = (day + 1).toString().padStart(2, '0');

    return `${year}-${formattedMonth}-${formattedDay}`;
  });
}

export function generateMockedBinaryListOfIncidentsForMonth(year: number, month: number): number[] {
  const daysInMonth = new Date(year, month, 0).getDate();

  return Array.from({ length: daysInMonth }, (_, i) => (i === 1 ? 1 : 0));
}
