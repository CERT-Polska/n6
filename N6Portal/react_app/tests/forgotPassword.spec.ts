import { test, expect, Page, Locator } from '@playwright/test';
import {
  expectToBeVisibleAndEnabled,
  fillInput,
  MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR,
  verifyInput
} from './utils/tools';
import { MockedApi } from './utils/mockedApi';
import { dictionary } from '../src/dictionary';

const fillLoginInput = async (input: Locator, email: string) => {
  await input.fill(email);
  await expect(input).toHaveValue(email);
};

test('Verify routing from the Login page to the Reset Password page', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('forgotPasswordLink').click();
  await page.waitForURL('/password-reset');
  expect(page.url()).toEqual('https://localhost/password-reset');
});

test.describe('Forgot password', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/password-reset');
  });

  test('Verify Forgot Password page', async ({ page }) => {
    await expect(page.getByTestId('n6Logo')).toBeVisible();
    await expect(page.getByTestId('resetPasswordHeading')).toBeVisible();
    await expect(page.getByText('Enter the email address')).toBeVisible();
    await verifyInput(page, 'loginInputResetPassword');

    const resetButton = page.getByTestId('resetPasswordBtn');
    await expectToBeVisibleAndEnabled(resetButton);

    const cancelButton = page.getByTestId('cancelBtnResetPassword');
    await expectToBeVisibleAndEnabled(cancelButton);
  });

  test.describe('verify flow:', () => {
    test.describe('Success flow', async () => {
      test('Valid e-mail and show success page', async ({ page }) => {
        const input = page.getByTestId('loginInputResetPassword');
        await fillLoginInput(input, 'user@example.com');

        await page.getByTestId('resetPasswordBtn').click();

        await expect(page.getByTestId('success-icon')).toBeVisible();
        await expect(page.getByTestId('forgot-password-success-description')).toBeVisible();
        await expect(page.getByText('We sent you a password reset link')).toBeVisible();

        const okBtn = page.getByTestId('forgot-password-success-ok-btn');
        await expectToBeVisibleAndEnabled(okBtn);
        await okBtn.click();
        await page.waitForURL('/');
        expect(page.url()).toEqual('https://localhost/');
        await expect(page.getByTestId('loginBtn')).toBeVisible();
      });
    });

    test.describe('Error flow', async () => {
      test('Show error page on 500 code', async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/password/forgotten', {}, 500);
        const input = page.getByTestId('loginInputResetPassword');
        await fillLoginInput(input, 'user@example.com');

        const resetPasswordBtn = page.getByTestId('resetPasswordBtn');
        await resetPasswordBtn.click();

        await expect(page.getByTestId('error-icon')).toBeVisible();
        await expect(page.getByTestId('forgot-password-error-title')).toBeVisible();
        await expect(page.getByTestId('forgot-password-error-description')).toBeVisible();

        const tryAgainButton = page.getByTestId('forgot-password-tryAgain-btn');
        await expectToBeVisibleAndEnabled(tryAgainButton);

        await tryAgainButton.click();
        await expect(resetPasswordBtn).toBeVisible();
      });
    });
  });

  test.describe('Invalid e-mail:', () => {
    const verifyResetPasswordErrorBehavior = async (input: Locator, page: Page, expectedInputValue: string) => {
      await page.getByTestId('resetPasswordBtn').click();
      await expect(input).toHaveValue(expectedInputValue);
      await expect(page.getByText('The entered login is not a valid e-mail address')).toBeVisible();
    };

    test('with a capital letters', async ({ page }) => {
      const input = page.getByTestId('loginInputResetPassword');
      await fillLoginInput(input, 'userTest@example.com');

      await verifyResetPasswordErrorBehavior(input, page, 'userTest@example.com');
    });

    test('with a non-capital letters', async ({ page }) => {
      const input = page.getByTestId('loginInputResetPassword');
      await fillLoginInput(input, 'test');

      await verifyResetPasswordErrorBehavior(input, page, 'test');
    });

    test('empty', async ({ page }) => {
      await page.getByTestId('resetPasswordBtn').click();
      await expect(page.getByText('Required field')).toBeVisible();
    });
  });
});

test.describe('Reset password', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/password-reset?token=${MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR}`);
  });

  test('Verify reset password page', async ({ page }) => {
    await expect(page.getByTestId('n6Logo')).toBeVisible();
    await expect(page.getByTestId('reset-password-title')).toBeVisible();
    await expectToBeVisibleAndEnabled(page.getByTestId('new-password-input'));
    await expectToBeVisibleAndEnabled(page.getByTestId('repeat-new-password-input'));
    await expect(page.getByTestId('reset-password-submit-btn')).toBeVisible();
  });

  test.describe('verify flow:', () => {
    const expectResetPasswordSuccessPage = async (page: Page) => {
      await expect(page.getByTestId('success-icon')).toBeVisible();
      await expect(page.getByTestId('reset-password-success-title')).toBeVisible();
      await expect(page.getByTestId('reset-password-success-descritpion')).toBeVisible();
      await expectToBeVisibleAndEnabled(page.getByTestId('reset-password-success-login-btn'));
    };

    const expectResetPasswordErrorPage = async (page: Page) => {
      await expect(page.getByTestId('error-icon')).toBeVisible();
      await expect(page.getByTestId('reset-password-error-title')).toBeVisible();
      await expectToBeVisibleAndEnabled(page.getByTestId('reset-password-error-tryAgain-btn'));
    };

    const fillResetPasswordFormWithValidCredentials = async (page: Page) => {
      await fillInput(page, 'new-password-input', 'Password1234');
      await fillInput(page, 'repeat-new-password-input', 'Password1234');
    };

    test.describe('Success flow', () => {
      test.beforeEach(async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/password/reset', {});
        await fillResetPasswordFormWithValidCredentials(page);
        await page.getByTestId('reset-password-submit-btn').click();
      });

      test('provide valid credentials and show Reset Password Success page', async ({ page }) => {
        await expectResetPasswordSuccessPage(page);
      });

      test('verify flow between Reset Password Success page -> Login page', async ({ page }) => {
        await page.getByTestId('reset-password-success-login-btn').click();
        await page.waitForURL('/');

        expect(page.url()).toEqual('https://localhost/');
        await expect(page.getByTestId('loginBtn')).toBeVisible();
      });
    });

    test.describe('Error flow', () => {
      test.beforeEach(async ({ page }) => {
        await MockedApi.mockApiRoute(page, '/api/password/reset', {}, 500);
        await fillResetPasswordFormWithValidCredentials(page);
        await page.getByTestId('reset-password-submit-btn').click();
      });

      test('provide valid credentials and show Reset Password Error page on 500', async ({ page }) => {
        await expectResetPasswordErrorPage(page);
      });

      test('verify flow between Reset Password Error page -> Forgot Password page', async ({ page }) => {
        await page.getByTestId('reset-password-error-tryAgain-btn').click();
        await page.waitForURL('/password-reset');

        expect(page.url()).toEqual('https://localhost/password-reset');
        await expect(page.getByTestId('resetPasswordHeading')).toBeVisible();
      });
    });

    test.describe('Invalid password', () => {
      test('validation constraints', async ({ page }) => {
        await fillInput(page, 'new-password-input', 'test', { blur: true });

        await expect(page.getByText(dictionary.en.validation_mustBePassword)).toBeVisible();
      });

      test('password difference', async ({ page }) => {
        await fillInput(page, 'new-password-input', 'Password1234', { blur: true });
        await fillInput(page, 'repeat-new-password-input', 'Different_password1', { blur: true });

        await expect(page.getByTestId('reset-password-difference-message')).toBeVisible();
      });
    });
  });
});
