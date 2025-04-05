import { expect, test, Page } from '@playwright/test';
import { MFA_CONFIG_RESPONSE, MOCKED_SETUP_MFA_RESPONSE, MockedApi } from './utils/mockedApi';
import { listOfUsers, MockedUser } from './utils/mockedUsers';
import { TestRunner } from './utils/TestRunner';
import { expectToBeVisibleAndEnabled, MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR } from './utils/tools';

function execUserSettingsTests(user: MockedUser) {
  test.describe(`User Settings - ${user.name}`, () => {
    test('check page title', async ({ page }) => {
      await expect(page.getByTestId('user-settings-title')).toBeVisible();
      await expect(page.getByTestId('user-settings-mfa-title')).toBeVisible();
    });

    test.describe('MFA', () => {
      test.describe('not configured MFA', () => {
        test.beforeEach(async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/mfa_config', {}, 403);
        });

        test('shows non configured MFA component', async ({ page }) => {
          await expect(page.getByTestId('user-settings-mfa-title')).toBeVisible();
          await expect(page.getByTestId('user-settings-mfa-config-section')).toBeVisible();
          await expect(page.getByTestId('user-settings-mfa-config-title')).toBeVisible();
          await expectToBeVisibleAndEnabled(page.getByTestId('user-settings-mfa-config-cta-btn'));
        });

        test('`configure new` button displays setup MFA component', async ({ page }) => {
          const eraseAndConfigureNewButton = page.getByTestId('user-settings-mfa-config-cta-btn');
          await MockedApi.mockApiRoute(page, '/api/mfa_config', {}, 200);

          await eraseAndConfigureNewButton.click();

          await expect(page.getByTestId('user-settings-login-mfa-config-title')).toBeVisible();
        });
      });

      test.describe('already configured MFA', () => {
        test.beforeEach(async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/mfa_config', { mfa_config: MFA_CONFIG_RESPONSE }, 200);
        });

        test('shows MFA component', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/mfa_config', { mfa_config: MFA_CONFIG_RESPONSE }, 200);

          await expect(page.getByTestId('user-settings-mfa-title')).toBeVisible();
          await expect(page.getByTestId('user-settings-mfa-edit-section')).toBeVisible();
          await expect(page.getByTestId('mfa_qr_code')).toBeVisible();
          await expect(page.getByTestId('mfa_key_label')).toBeVisible();
          await expect(page.getByTestId('mfa_secret_key')).toBeVisible();
          await expectToBeVisibleAndEnabled(page.getByTestId('user-settings-mfa-edit-cta-btn'));
        });

        test('`erase and configure new` button displays setup MFA component', async ({ page }) => {
          const eraseAndConfigureNewButton = page.getByTestId('user-settings-mfa-edit-cta-btn');
          await eraseAndConfigureNewButton.click();

          await expect(page.getByTestId('user-settings-login-mfa-config-title')).toBeVisible();
          await expect(page.getByTestId('mfa_qr_code')).toBeVisible();
        });
      });
    });

    test.describe('API Key Section', () => {
      const expectAPIKeyInPlaceholder = async (page: Page, value?: string) => {
        const textArea = page.getByTestId('user-settings-api-key-input');
        await expect(textArea).toBeVisible();
        await expect(textArea).not.toBeEditable();
        await expect(textArea).toHaveText(value);
        await expect(textArea).toHaveValue(value);
      };

      if (user.api_key_auth_enabled) {
        test('displays API key for existing key', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/api_key', {
            api_key: MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR
          });

          await expectAPIKeyInPlaceholder(page, MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR);
        });

        test.beforeEach(async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/api_key', { api_key: null });
        });

        test('renders default view', async ({ page }) => {
          await expect(page.getByTestId('user-settings-api-key-section')).toBeVisible();
          await expect(page.getByTestId('user-settings-api-key-title')).toBeVisible();

          const removeKeyBtn = page.getByTestId('user-settings-api-key-remove-btn');
          await expect(removeKeyBtn).toBeVisible();
          await expect(removeKeyBtn).toBeDisabled();

          const generateKeyBtn = page.getByTestId('user-settings-api-key-generate-btn');
          await expectToBeVisibleAndEnabled(generateKeyBtn);
        });

        test('does not display API key due to not existing key', async ({ page }) => {
          await expectAPIKeyInPlaceholder(page, '');
        });

        test.describe('Create, Remove, Regenerate API key', () => {
          test.beforeEach(async ({ page }) => {
            const generateKeyBtn = page.getByTestId('user-settings-api-key-generate-btn');
            await generateKeyBtn.click();
            await MockedApi.mockApiRoute(page, '/api/api_key', {
              api_key: MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR
            });
          });

          test.describe('verify modal', () => {
            const expectModal = async (page: Page) => {
              await expect(page.getByTestId('user-settings-confirmation-modal')).toBeVisible();
              await expect(page.getByTestId('user-settings-confirmation-title')).toBeVisible();
              await expect(page.getByTestId('user-settings-confirmation-description')).toBeVisible();
              await expectToBeVisibleAndEnabled(page.getByTestId('user-settings-confirmation-cancel-btn'));
              await expectToBeVisibleAndEnabled(page.getByTestId('user-settings-confirmation-confirm-btn'));
            };

            const cancelAndExpectModalToNotBeVisible = async (page: Page) => {
              const cancelBtn = page.getByTestId('user-settings-confirmation-cancel-btn');
              await cancelBtn.click();

              await expect(page.getByTestId('user-settings-confirmation-modal')).not.toBeVisible();
            };

            test('renders modal for removing the key and check cancel modal', async ({ page }) => {
              const removeKeyBtn = page.getByTestId('user-settings-api-key-remove-btn');
              await removeKeyBtn.click();

              await expectModal(page);
              await cancelAndExpectModalToNotBeVisible(page);
            });

            test('renders modal for regenerating the key and check cancel modal', async ({ page }) => {
              const generateKeyBtn = page.getByTestId('user-settings-api-key-generate-btn');
              await generateKeyBtn.click();

              await expectModal(page);
              await cancelAndExpectModalToNotBeVisible(page);
            });
          });

          test('generate a new key', async ({ page }) => {
            await expect(page.getByTestId('user-settings-api-key-input')).toHaveValue(
              MOCKED_JWT_TOKEN_WITH_EXPIRE_DATE_TO_2050_YEAR
            );
          });

          test('remove generated key', async ({ page }) => {
            const removeKeyBtn = page.getByTestId('user-settings-api-key-remove-btn');
            await removeKeyBtn.click();

            const confirmBtn = page.getByTestId('user-settings-confirmation-confirm-btn');

            await MockedApi.mockApiRoute(page, '/api/api_key', {});
            await MockedApi.mockApiRoute(page, '/api/api_key', { api_key: null });
            await confirmBtn.click();

            await expect(page.getByTestId('user-settings-api-key-input')).toHaveValue('');
          });
        });
      } else {
        test('API key section does not render for api_key_auth disabled', async ({ page }) => {
          await expect(page.getByTestId('user-settings-api-key-section')).not.toBeVisible();
        });

        test('the MFA config appears', async ({ page }) => {
          await MockedApi.mockApiRoute(page, '/api/mfa_config', { mfa_config: MFA_CONFIG_RESPONSE }, 200);

          await expect(page.getByTestId('user-settings-mfa-edit-section')).toBeVisible();
        });
      }
    });
  });
}

const runner = TestRunner.builder
  .withTestName('User Settings Tests')
  .withUsers(listOfUsers)
  .withBeforeEach(async (page, user) => {
    await MockedApi.getUserInfo(page, user);
    await page.goto('/user-settings');
  })
  .withTests((user) => {
    execUserSettingsTests(user);
  })
  .build();

runner.runTests();
