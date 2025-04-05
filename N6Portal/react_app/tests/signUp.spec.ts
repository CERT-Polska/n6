import { expect, Page, test } from '@playwright/test';
import { expectToBeVisibleAndEnabled, fillInput } from './utils/tools';
import { dictionary } from '../src/dictionary';
import { MockedApi } from './utils/mockedApi';

const fieldsTestData = [
  {
    label: 'Organization domain',
    labelID: 'signupTwo-org-input_label',
    inputID: 'signupTwo-org-input',
    validValue: 'validdomain.com',
    invalidValue: '@test',
    validationErrorMsg: 'Please eneter valid organization domain',
    addBtnTestId: undefined,
    tooltip_testid: 'singupTwo-tooltip-org',
    tooltip_text: dictionary.en.signup_domain_tooltip
  },
  {
    label: 'Entity name',
    labelID: 'signupTwo-actual-name-input_label',
    inputID: 'signupTwo-actual-name-input',
    validValue: 'Valid entity name',
    invalidValue: '@test',
    validationErrorMsg: 'Some characters are not allowed',
    addBtnTestId: undefined,
    tooltip_testid: 'singupTwo-tooltip-actual-name',
    tooltip_text: dictionary.en.signup_entity_tooltip
  },
  {
    label: 'E-mail',
    labelID: 'signupTwo-email-input_label',
    inputID: 'signupTwo-email-input',
    validValue: 'valid@email.com',
    invalidValue: '@test',
    validationErrorMsg: 'Invalid e-mail address',
    addBtnTestId: undefined,
    tooltip_testid: 'singupTwo-tooltip-email',
    tooltip_text: dictionary.en.signup_email_tooltip
  },
  {
    label: 'Company title',
    labelID: 'singupTwo-submitter-title-input_label',
    inputID: 'singupTwo-submitter-title-input',
    validValue: 'Valid company title',
    invalidValue: '@test',
    validationErrorMsg: 'Some characters are not allowed',
    addBtnTestId: undefined,
    tooltip_testid: 'singupTwo-tooltip-submitter-title',
    tooltip_text: dictionary.en.signup_position_tooltip
  },
  {
    label: 'First and last name',
    labelID: 'singupTwo-submitter-name-input_label',
    inputID: 'singupTwo-submitter-name-input',
    validValue: 'John Doe',
    invalidValue: '123 test',
    validationErrorMsg: 'Some characters are not allowed',
    addBtnTestId: undefined,
    tooltip_testid: 'singupTwo-tooltip-submitter-name',
    tooltip_text: dictionary.en.signup_fullName_tooltip
  },
  {
    label: 'E-mail address for notifications',
    labelID: 'notification_emails-entry-input_label',
    inputID: 'notification_emails-entry-input',
    validValue: 'valid@email.com',
    invalidValue: 'invalidemail',
    validationErrorMsg: 'Invalid e-mail address',
    addBtnTestId: 'notification_emails-add-btn',
    tooltip_testid: 'signupTwo-tooltip-notification-email',
    tooltip_text: dictionary.en.signup_notificationEmails_tooltip
  },
  {
    label: 'ASN',
    labelID: 'asns-entry-input_label',
    inputID: 'asns-entry-input',
    validValue: '1111',
    invalidValue: 'test',
    validationErrorMsg: 'Value must be number',
    addBtnTestId: 'asns-add-btn',
    tooltip_testid: 'signupTwo-tooltip-notification-asns',
    tooltip_text: dictionary.en.signup_asn_tooltip
  },
  {
    label: 'FQDN',
    labelID: 'fqdns-entry-input_label',
    inputID: 'fqdns-entry-input',
    validValue: 'exampledomain.com',
    invalidValue: '@test',
    validationErrorMsg: 'Please eneter valid organization domain',
    addBtnTestId: 'fqdns-add-btn',
    tooltip_testid: 'signupTwo-tooltip-notification-fqdns',
    tooltip_text: dictionary.en.signup_fqdn_tooltip
  },
  {
    label: 'IP network',
    labelID: 'ip_networks-entry-input_label',
    inputID: 'ip_networks-entry-input',
    validValue: '1.1.1.1/23',
    invalidValue: 'test',
    validationErrorMsg: 'Please enter valid IP address (CIDR)',
    addBtnTestId: 'ip_networks-add-btn',
    tooltip_testid: 'signupTwo-tooltip-notification-ipNetworks',
    tooltip_text: dictionary.en.signup_ipNetwork_tooltip
  }
];

test('Routing: Login -> Sign-up (1/2) page', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('createAccountBtn').click();
  await page.waitForURL('/sign-up');
  expect(page.url()).toEqual('https://localhost/sign-up');
});

test.beforeEach(async ({ page }) => {
  await page.goto('/sign-up');
});

test.describe('Sign-up - step 1/2', async () => {
  test('Display Sign-up page (1/2)', async ({ page }) => {
    await expect(page.getByTestId('n6Logo')).toBeVisible();
    await expect(page.getByText('Sign-up form (1/2)')).toBeVisible();

    await expectToBeVisibleAndEnabled(page.getByTestId('languagePickerEN'));
    await expectToBeVisibleAndEnabled(page.getByTestId('languagePickerPL'));

    await expect(page.getByText('The n6 platform provides')).toBeVisible();
    await expect(page.getByText('Data in n6 come from various')).toBeVisible();
    await expect(page.getByText('System administrator is not')).toBeVisible();

    const checkBox = page.getByTestId('signup-terms-checkbox');
    await expectToBeVisibleAndEnabled(checkBox);
    await expect(checkBox).not.toBeChecked();

    await expectToBeVisibleAndEnabled(page.getByTestId('signup-submit-btn'));
    await expectToBeVisibleAndEnabled(page.getByTestId('signup-cancel-btn'));
  });

  test('Language picker behaviour', async ({ page }) => {
    const langEnBtn = page.getByTestId('languagePickerEN');
    const langPlBtn = page.getByTestId('languagePickerPL');

    await langPlBtn.click();
    await expect(page.getByText('Dostęp i prawo do korzystania')).toBeVisible();

    await langEnBtn.click();
    await expect(page.getByText('Your access to and use')).toBeVisible();
  });

  test('Checkbox behaviour', async ({ page }) => {
    const checkBox = page.getByTestId('signup-terms-checkbox');
    await checkBox.check();
    await expect(checkBox).toBeChecked();
    await checkBox.uncheck();
    await expect(checkBox).not.toBeChecked();
  });

  test('Unchecked checkbox flow account creation', async ({ page }) => {
    const createAccountBtn = page.getByTestId('signup-submit-btn');
    await createAccountBtn.click();
    await expect(page.getByText('Required field')).toBeVisible();
  });
});

test.describe('Sign-up - step 2/2', async () => {
  test.beforeEach(async ({ page }) => {
    await page.getByTestId('signup-terms-checkbox').check();
    await page.getByTestId('signup-submit-btn').click();
    await page.waitForURL('/sign-up');
  });

  const checkInput = async (
    label: string,
    labelId: string,
    testId: string,
    tooltipTestId: string,
    tooltipText: string,
    page: Page,
    addBtnTestId?: string
  ) => {
    const input = page.getByTestId(testId);
    await expect(page.getByTestId(labelId)).toContainText(label);
    await expectToBeVisibleAndEnabled(input);
    await expect(input).toBeEmpty();

    const tooltipBtn = page.getByTestId(tooltipTestId);
    await expectToBeVisibleAndEnabled(tooltipBtn);
    await tooltipBtn.hover();
    await expect(page.getByText(tooltipText)).toBeVisible();

    await expect(page.getByTestId(tooltipTestId)).toBeVisible();

    if (addBtnTestId) {
      await expectToBeVisibleAndEnabled(page.getByTestId(addBtnTestId));
    }
  };

  test('Routing: Sign-up (1/2) -> Sign-up (2/2) page', async ({ page }) => {
    await expect(page.getByText('Sign-up form (2/2)')).toBeVisible();
  });

  test('Display Sign-up page (2/2)', async ({ page }) => {
    for (const field of fieldsTestData) {
      await checkInput(
        field.label,
        field.labelID,
        field.inputID,
        field.tooltip_testid,
        field.tooltip_text,
        page,
        field.addBtnTestId
      );
    }

    await expect(page.getByText('Language of notifications')).toBeVisible();
    await expect(page.getByTestId('singupTwo-tooltip-notification-lang')).toBeVisible();

    await expectToBeVisibleAndEnabled(page.getByTestId('singupTwo-notification-lang-input-radio-EN'));
    await expectToBeVisibleAndEnabled(page.getByTestId('singupTwo-notification-lang-input-radio-PL'));

    await expectToBeVisibleAndEnabled(page.getByTestId('signup-submit-btn'));
    await expectToBeVisibleAndEnabled(page.getByTestId('signup-cancel-btn'));
  });

  test.describe('Form validation:', async () => {
    const checkValidValue = async (inputId: string, value: string, validationErrorMsg: string, page: Page) => {
      const input = await fillInput(page, inputId, value, { blur: true });

      await expect(input).toHaveValue(value);
      await expect(page.getByText(validationErrorMsg)).not.toBeVisible();
    };

    const expectValidationErrorMessage = async (
      inputId: string,
      value: string,
      validationErrorMsg: string,
      page: Page
    ) => {
      const input = await fillInput(page, inputId, value, { blur: true });

      await expect(page.getByText(validationErrorMsg)).toBeVisible();
      await input.clear();
    };

    test('each field should accept valid value', async ({ page }) => {
      for (const field of fieldsTestData) {
        await checkValidValue(field.inputID, field.validValue, field.validationErrorMsg, page);
      }
    });

    test('should show validation error message for each field with invalid value', async ({ page }) => {
      for (const field of fieldsTestData) {
        await expectValidationErrorMessage(field.inputID, field.invalidValue, field.validationErrorMsg, page);
      }
    });

    test('should show `required field` error for field with empty value', async ({ page }) => {
      await page.getByTestId('signup-submit-btn').click();
      const errorMsgs = page.locator('text="Required field"');
      expect(await errorMsgs.count()).toEqual(6);
    });
  });

  test.describe('Form submission', async () => {
    const submitAndWait = async (page: Page) => {
      await page.getByTestId('signup-submit-btn').click();
      await page.waitForURL('/sign-up');
    };

    test.beforeEach(async ({ page }) => {
      for (const field of fieldsTestData) {
        await fillInput(page, field.inputID, field.validValue, { blur: true });
      }
      await page.getByTestId('singupTwo-notification-lang-input-radio-EN').check();
    });

    test('should show success page', async ({ page }) => {
      await submitAndWait(page);
      await expect(page.getByText('The registration form has been sent')).toBeVisible();
      await expect(page.getByTestId('success-icon')).toBeVisible();
    });

    test('should check if `Go to login page` button works', async ({ page }) => {
      await submitAndWait(page);
      const goToLoginPageBtn = page.getByTestId('signupSuccess-backToLoginPage-btn');
      await expectToBeVisibleAndEnabled(goToLoginPageBtn);
      await goToLoginPageBtn.click();
      await page.waitForURL('/');

      expect(page.url()).toEqual('https://localhost/');
      await expect(page.getByText('Log in')).toBeVisible();
    });

    test('should show error if form has not been sent correct', async ({ page }) => {
      await MockedApi.mockApiRoute(page, '/api/register', {}, 500);
      await submitAndWait(page);

      await expect(page.getByText('There was an error while')).toBeVisible();
    });
  });
});
