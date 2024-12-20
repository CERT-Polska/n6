/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from 'react-query';
import { IntlProvider } from 'react-intl';
import userEvent from '@testing-library/user-event';
import { toast } from 'react-toastify';
import { IOrgConfig } from 'api/orgConfig/types';
import { postOrgConfig } from 'api/orgConfig';
import EditSettingsForm from 'components/pages/editSettings/EditSettingsForm';
import { dictionary } from 'dictionary';

interface ValidationTestCase {
  fieldName: string;
  invalidValue: string;
  validValue: string;
  errorMessageKey: string;
  expectedFieldCount: number;
  fieldIndex?: number;
}
// Types
type Locale = 'en' | 'pl';

// Constants
const TEST_TIMEOUT = 15000;
const MAX_COMMENT_LENGTH = 4000;

// Test configuration
jest.mock('api/orgConfig');
jest.mock('react-toastify');
jest.mock('components/shared/Tooltip', () => ({
  __esModule: true,
  default: ({ content, id, children }: { content: string; id: string; children: React.ReactNode }) => (
    <div data-testid={`tooltip-${id}`} data-tooltip-content={content}>
      {children}
    </div>
  )
}));
beforeEach(() => {
  jest.clearAllMocks();
  jest.resetAllMocks();
});

HTMLElement.prototype.scrollIntoView = jest.fn();
window.scroll = jest.fn();

const mockPostOrgConfig = postOrgConfig as jest.MockedFunction<typeof postOrgConfig>;
const queryClient = new QueryClient();

// Test utilities and setup
const defaultCurrentSettings: IOrgConfig = {
  org_id: 'test-org',
  actual_name: 'Test Org',
  org_user_logins: ['user1@test.com'],
  asns: [1234],
  fqdns: ['domain1.com', 'domain2.com'],
  ip_networks: ['192.168.1.0/24'],
  notification_enabled: true,
  notification_language: 'EN',
  notification_emails: ['notify@test.com'],
  notification_times: ['10:00'],
  post_accepted: null,
  update_info: null
};

const renderComponent = (lang: Locale = 'en', currentSettings = defaultCurrentSettings) => {
  return render(
    <QueryClientProvider client={queryClient}>
      <IntlProvider messages={dictionary[lang]} locale={lang}>
        <EditSettingsForm currentSettings={currentSettings} />
      </IntlProvider>
    </QueryClientProvider>
  );
};

const testFieldValidation = async (
  lang: Locale,
  renderComponent: (lang: Locale) => void,
  testCase: ValidationTestCase
) => {
  renderComponent(lang);

  const entryField = screen.getByTestId(`${testCase.fieldName}-entry-field`);
  const input = within(entryField).getByRole('textbox');
  const addButton = within(entryField).getByLabelText(`${testCase.fieldName}-add-button`);

  // Test invalid input
  await userEvent.type(input, testCase.invalidValue);
  await userEvent.click(addButton);

  expect(
    screen.getByText(dictionary[lang][testCase.errorMessageKey as keyof (typeof dictionary)[typeof lang]])
  ).toBeInTheDocument();

  // Test valid input
  await userEvent.clear(input);
  await userEvent.type(input, testCase.validValue);
  await userEvent.click(addButton);

  const fields = screen.getAllByTestId(new RegExp(`${testCase.fieldName}-field-`, 'i'));
  expect(fields).toHaveLength(testCase.expectedFieldCount);
  expect(within(fields[testCase.fieldIndex ?? 1]).getByRole('textbox')).toHaveValue(testCase.validValue);
};

describe('EditSettingsForm', () => {
  describe('Initial Rendering', () => {
    it.each(['en', 'pl'] as const)('renders form with default values (%s)', (lang) => {
      renderComponent(lang);

      // Organization info assertions
      expect(screen.getByDisplayValue('test-org')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Test Org')).toBeInTheDocument();
      expect(screen.getByDisplayValue('user1@test.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('domain1.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('domain2.com')).toBeInTheDocument();

      // Text elements from dictionary
      expect(screen.getByText(dictionary[lang]['edit_settings_title'])).toBeInTheDocument();
      expect(screen.getByText(dictionary[lang]['signup_domain_label'])).toBeInTheDocument();
      expect(screen.getByText(dictionary[lang]['signup_entity_label'])).toBeInTheDocument();

      // Network settings
      expect(screen.getByDisplayValue('192.168.1.0/24')).toBeInTheDocument();
      expect(screen.getByDisplayValue('1234')).toBeInTheDocument();

      // Notification settings
      expect(
        screen.getByRole('checkbox', { name: dictionary[lang]['edit_settings_notification_enabled_label'] })
      ).toBeChecked();
      expect(screen.getByDisplayValue('notify@test.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('10:00')).toBeInTheDocument();
      expect(screen.getByDisplayValue('EN')).toBeInTheDocument();

      // Form structure
      expect(screen.getAllByRole('textbox')).toHaveLength(16);
    });

    it.each(['en', 'pl'] as const)('renders tooltips with correct content (%s)', (lang) => {
      renderComponent(lang);

      const tooltipConfigs = [
        { id: 'org_id', messageKey: 'signup_domain_tooltip' },
        { id: 'actual_name', messageKey: 'signup_entity_tooltip' },
        { id: 'notification_enabled', messageKey: 'edit_settings_notification_enabled_tooltip' },
        { id: 'notification_language', messageKey: 'signup_lang_tooltip' },
        { id: 'notification_times', messageKey: 'edit_settings_notification_times_tooltip' },
        { id: 'notification_emails', messageKey: 'signup_notificationEmails_tooltip' },
        { id: 'fqdns', messageKey: 'signup_fqdn_tooltip' },
        { id: 'asns', messageKey: 'signup_asn_tooltip' },
        { id: 'ip_networks', messageKey: 'signup_ipNetwork_tooltip' },
        { id: 'additional_comment', messageKey: 'edit_settings_additional_comment_tooltip' }
      ];

      tooltipConfigs.forEach(({ id, messageKey }) => {
        const tooltip = screen.getByTestId(`tooltip-edit-settings${id === 'org_id' ? '_' : '-'}${id}`);
        expect(tooltip).toHaveAttribute(
          'data-tooltip-content',
          dictionary[lang][messageKey as keyof (typeof dictionary)[typeof lang]]
        );
      });
    });
  });

  describe('Form State Management', () => {
    describe('Update Info Handling', () => {
      const settingsWithUpdate = {
        ...defaultCurrentSettings,
        update_info: {
          update_request_time: '2024-01-01',
          requesting_user: 'user1',
          fqdns: ['domain1.com']
        }
      };

      it('merges default and updated values when update_info exists', () => {
        renderComponent(undefined, settingsWithUpdate);

        // Check active fields
        const fields = screen.getAllByTestId(/fqdns-field-/i);
        expect(fields).toHaveLength(1);

        const input = within(fields[0]).getByRole('textbox');
        expect(input).toHaveValue('domain1.com');

        // Check restore fields
        const restoreField = screen.getByTestId('fqdns-restore-field-0');
        expect(within(restoreField).getByRole('textbox')).toHaveValue('domain2.com');
      });

      it.each(['en', 'pl'] as const)('disables form when update_info exists (%s)', (lang) => {
        renderComponent(lang, settingsWithUpdate);

        // Check that all inputs are disabled
        const inputs = screen.getAllByRole('textbox');
        inputs.forEach((input) => {
          expect(input).toBeDisabled();
        });

        const buttons = [
          ...screen.getAllByLabelText(/-remove-button-/),
          ...screen.getAllByLabelText(/-add-button/),
          ...screen.getAllByLabelText(/-restore-button-/)
        ];
        buttons.forEach((button) => {
          expect(button).toBeDisabled();
        });
        // Check that submit button is disabled
        const submitButton = screen.getByRole('button', { name: dictionary[lang]['edit_settings_btn_submit'] });
        expect(submitButton).toBeDisabled();
      });

      it.each(['en', 'pl'] as const)('shows pending message when update_info exists (%s)', async (lang) => {
        renderComponent(lang, settingsWithUpdate);

        // Check pending info message
        await waitFor(() => {
          expect(screen.getByText(dictionary[lang]['edit_settings_pending_message'])).toBeInTheDocument();
        });

        await waitFor(() => {
          expect(screen.getByText(dictionary[lang]['edit_settings_pending_message_annotation'])).toBeInTheDocument();
        });
      });
    });

    describe('Reset Functionality', () => {
      it.each(['en', 'pl'] as const)('resets form when reset button is clicked (%s)', async (lang) => {
        renderComponent(lang);

        const actualNameInput = screen.getByDisplayValue('Test Org');
        await userEvent.clear(actualNameInput);
        await userEvent.type(actualNameInput, 'New Org Name');

        // Click reset button
        const resetButton = screen.getByText(dictionary[lang]['edit_settings_btn_reset']);
        await userEvent.click(resetButton);

        // Check that values are reset
        expect(screen.getByDisplayValue('Test Org')).toBeInTheDocument();
        expect(screen.queryByDisplayValue('New Org Name')).not.toBeInTheDocument();
      });

      it.each(['en', 'pl'] as const)('shows and handles field reset buttons (%s)', async () => {
        renderComponent();

        // Change actual name to make reset button appear
        const actualNameInput = screen.getByDisplayValue('Test Org');

        await userEvent.clear(actualNameInput);
        await userEvent.type(actualNameInput, 'Changed Name');
        await userEvent.tab();

        // Reset button should appear and work
        const resetButton = screen.getByRole('button', { name: '' });
        expect(resetButton).toHaveClass('reset-field-btn');
        await userEvent.click(resetButton);

        expect(screen.getByDisplayValue('Test Org')).toBeInTheDocument();

        // After reset - button disappears
        expect(screen.queryByRole('button', { name: '' })).not.toBeInTheDocument();
      });
    });
  });

  describe('Form Validation', () => {
    describe('Field-specific Validation', () => {
      const validationTestCases: ValidationTestCase[] = [
        {
          fieldName: 'ip_networks',
          invalidValue: '256.256.256.256/33',
          validValue: '192.168.1.0/24',
          errorMessageKey: 'validation_mustBeIpNetwork',
          expectedFieldCount: 2
        },
        {
          fieldName: 'asns',
          invalidValue: 'invalid',
          validValue: '64512',
          errorMessageKey: 'validation_mustBeNumber',
          expectedFieldCount: 2
        },
        {
          fieldName: 'notification_emails',
          invalidValue: 'invalid-email',
          validValue: 'valid@email.com',
          errorMessageKey: 'validation_mustBeEmail',
          expectedFieldCount: 2
        },
        {
          fieldName: 'org_user_logins',
          invalidValue: 'invalid-user',
          validValue: 'user@example.com',
          errorMessageKey: 'validation_mustBeEmail',
          expectedFieldCount: 2
        },
        {
          fieldName: 'fqdns',
          invalidValue: 'invalid..domain',
          validValue: 'valid.domain.com',
          errorMessageKey: 'validation_mustBeOrgDomain',
          expectedFieldCount: 3,
          fieldIndex: 2
        }
      ];

      validationTestCases.forEach((testCase) => {
        it.each(['en', 'pl'] as const)(`validates ${testCase.fieldName} inputs (%s)`, async (lang) => {
          await testFieldValidation(lang, renderComponent, testCase);
        });
      });

      // Special case for ASN additional validation
      it.each(['en', 'pl'] as const)('validates ASN range (%s)', async (lang) => {
        renderComponent(lang);
        const entryField = screen.getByTestId('asns-entry-field');
        const input = within(entryField).getByRole('textbox');
        const addButton = within(entryField).getByLabelText('asns-add-button');

        await userEvent.type(input, '4294967296');
        await userEvent.click(addButton);

        await waitFor(() => {
          expect(screen.getByText(dictionary[lang]['validation_mustBeAsnNumber'])).toBeInTheDocument();
        });
      });
    });
  });

  it.each(['en', 'pl'] as const)('revalidates form inputs after an invalid attempt (%s)', async (lang) => {
    renderComponent(lang);

    const emaiField = screen.getByTestId('notification_emails-entry-field');
    const emailInput = within(emaiField).getByRole('textbox');
    await userEvent.type(emailInput, 'invalid-email');
    fireEvent.blur(emailInput);

    const errorMessage = await screen.findByText(dictionary[lang]['validation_mustBeEmail']);
    expect(errorMessage).toBeInTheDocument();

    await userEvent.type(emailInput, 'notify@test.com');
    fireEvent.blur(emailInput);

    await waitFor(() => expect(screen.queryByText(dictionary[lang]['validation_mustBeEmail'])).not.toBeInTheDocument());
  });
});

describe('Form Submission', () => {
  const setupSubmissionTest = async (lang: 'en' | 'pl') => {
    renderComponent(lang);
    const actualNameInput = screen.getByDisplayValue('Test Org');
    await userEvent.clear(actualNameInput);
    await userEvent.type(actualNameInput, 'New Org Name');
    return screen.getByRole('button', { name: dictionary[lang]['edit_settings_btn_submit'] });
  };

  it.each(['en', 'pl'] as const)('shows success message after successful submission (%s)', async (lang) => {
    mockPostOrgConfig.mockResolvedValueOnce({
      ...defaultCurrentSettings,
      post_accepted: true
    });

    const submitButton = await setupSubmissionTest(lang);
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(dictionary[lang]['edit_settings_submit_message'])).toBeInTheDocument();
    });
  });

  it.each(['en', 'pl'] as const)('shows error message after failed submission (%s)', async (lang) => {
    mockPostOrgConfig.mockRejectedValueOnce(new Error('Failed'));

    const submitButton = await setupSubmissionTest(lang);
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(dictionary[lang]['edit_settings_submit_error'])).toBeInTheDocument();
    });
  });

  it.each(['en', 'pl'] as const)('does not allow submission if no changes are made (%s)', (lang) => {
    renderComponent(lang);
    const submitButton = screen.getByRole('button', { name: dictionary[lang]['edit_settings_btn_submit'] });
    expect(submitButton).toBeDisabled();
  });

  it.each(['en', 'pl'] as const)('shows error toast when form has validation errors on submit (%s)', async (lang) => {
    const mockToast = jest.fn();
    (toast as unknown as jest.Mock).mockImplementation(mockToast);
    const submitButton = await setupSubmissionTest(lang);

    // Add invalid email
    const emailField = screen.getByTestId('notification_emails-entry-field');
    const emailInput = within(emailField).getByRole('textbox');
    await userEvent.clear(emailInput);
    await userEvent.type(emailInput, 'invalid-email');
    await userEvent.tab();

    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(dictionary[lang]['edit_settings_form_error_message'], expect.any(Object));
    });
  });

  it.each(['en', 'pl'] as const)('refetches data after successful submission (%s)', async (lang) => {
    const mockRefetch = jest.fn();
    jest.spyOn(queryClient, 'refetchQueries').mockImplementation(mockRefetch);
    mockPostOrgConfig.mockResolvedValueOnce({
      ...defaultCurrentSettings,
      post_accepted: true
    });

    const submitButton = await setupSubmissionTest(lang);
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(mockRefetch).toHaveBeenCalledWith('orgConfig', undefined);
    });
  });

  describe('Form Submission Prevention', () => {
    const mockSubmitHandler = jest.fn();

    beforeEach(() => {
      mockSubmitHandler.mockClear();
    });

    const setupForm = () => {
      renderComponent();
      const form = screen.getByRole('form', { name: 'org-settings-form' });
      if (form) form.onsubmit = mockSubmitHandler;
      return form;
    };

    const getTestInput = () => {
      const entryField = screen.getByTestId('fqdns-entry-field');
      return within(entryField).getByRole('textbox');
    };

    it('prevents form submission when pressing Enter in entry field', async () => {
      setupForm();
      const input = getTestInput();

      await userEvent.type(input, 'test.domain.com{enter}');
      expect(mockSubmitHandler).not.toHaveBeenCalled();
    });

    it('prevents form submission when pressing Enter in existing fields', async () => {
      setupForm();

      const fields = screen.getAllByTestId(/fqdns-field-/i);

      for (const field of fields) {
        const input = within(field).getByRole('textbox');
        await userEvent.type(input, '{enter}');
      }
      expect(mockSubmitHandler).not.toHaveBeenCalled();
    });

    it('correctly removes event listener on component unmount', async () => {
      const addEventListenerSpy = jest.spyOn(document, 'addEventListener');
      const removeEventListenerSpy = jest.spyOn(document, 'removeEventListener');

      const { unmount } = renderComponent();

      expect(addEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));
      unmount();
      expect(removeEventListenerSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

      addEventListenerSpy.mockRestore();
      removeEventListenerSpy.mockRestore();
    });

    it('allows normal typing in fields while preventing Enter submission', async () => {
      setupForm();
      const input = getTestInput();

      await userEvent.type(input, 'test.domain.com');
      expect(input).toHaveValue('test.domain.com');

      await userEvent.type(input, '{enter}');
      expect(mockSubmitHandler).not.toHaveBeenCalled();
      expect(input).toHaveValue('test.domain.com');
    });

    it('maintains other keyboard functionality while preventing Enter submission', async () => {
      setupForm();
      const input = getTestInput();

      await userEvent.type(input, 'test{backspace}{backspace}');
      expect(input).toHaveValue('te');

      await userEvent.type(input, '{arrowleft}{arrowleft}s{arrowright}{arrowright}k');
      expect(input).toHaveValue('stek');

      expect(mockSubmitHandler).not.toHaveBeenCalled();
    });

    it('prevents form submission via Enter in any input field', async () => {
      setupForm();

      const inputs = screen.getAllByRole('textbox');

      for (const input of inputs) {
        await userEvent.type(input, '{enter}');
        expect(mockSubmitHandler).not.toHaveBeenCalled();
      }
    });

    it('prevents form submission via Enter when combined with modifier keys', async () => {
      setupForm();
      const input = getTestInput();

      await userEvent.type(input, '{Shift>}{enter}{/Shift}');
      expect(mockSubmitHandler).not.toHaveBeenCalled();

      await userEvent.type(input, '{Control>}{enter}{/Control}');
      expect(mockSubmitHandler).not.toHaveBeenCalled();
    });
  });
});

describe('Form Controls', () => {
  describe('Notification Settings', () => {
    it('handles notification_times field array operations', async () => {
      renderComponent();

      const entryField = screen.getByTestId('notification_times-entry-field');
      const input = within(entryField).getByRole('textbox');
      const addButton = within(entryField).getByLabelText('notification_times-add-button');

      // Add new time
      await userEvent.type(input, '12:00');
      await userEvent.click(addButton);

      const fields = screen.getAllByTestId(/notification_times-field-/i);
      expect(fields).toHaveLength(2); // Original + new one
      expect(within(fields[1]).getByRole('textbox')).toHaveValue('12:00');

      // Remove time
      const removeButton = within(fields[1]).getByLabelText('notification_times-remove-button-1');
      await userEvent.click(removeButton);

      await waitFor(() => {
        const remainingFields = screen.getAllByTestId(/notification_times-field-/i);
        expect(remainingFields).toHaveLength(1);
      });
    });

    it.each(['en', 'pl'] as const)('handles notification language selection (%s)', async (lang) => {
      renderComponent(lang);

      const enRadio = screen.getByLabelText(dictionary[lang]['language_picker_en_short']);
      const plRadio = screen.getByLabelText(dictionary[lang]['language_picker_pl_short']);

      // Default should be EN
      expect(enRadio).toBeChecked();
      expect(plRadio).not.toBeChecked();

      // Change to PL
      await userEvent.click(plRadio);
      expect(plRadio).toBeChecked();
      expect(enRadio).not.toBeChecked();
    });

    it.each(['en', 'pl'] as const)('handles notification enabled toggle (%s)', async (lang) => {
      renderComponent(lang);

      const checkbox = screen.getByRole('checkbox', {
        name: dictionary[lang]['edit_settings_notification_enabled_label']
      });

      // Default should be checked based on current settings
      expect(checkbox).toBeChecked();

      // Toggle off
      await userEvent.click(checkbox);
      expect(checkbox).not.toBeChecked();
    });
  });

  it.each(['en', 'pl'] as const)(
    'handles additional comment input (%s)',
    async (lang) => {
      renderComponent(lang);

      const textarea = screen.getByRole('textbox', {
        name: dictionary[lang]['edit_settings_additional_comment_label']
      });

      const exactLengthComment = 'a'.repeat(MAX_COMMENT_LENGTH);
      await userEvent.type(textarea, exactLengthComment + 'extra');

      // Should only contain 4000 characters
      expect(textarea).toHaveValue(exactLengthComment);
      expect((textarea as HTMLTextAreaElement).value).toHaveLength(MAX_COMMENT_LENGTH);
    },
    TEST_TIMEOUT
  );
});
// });
