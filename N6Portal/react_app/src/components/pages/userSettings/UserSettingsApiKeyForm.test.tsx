import { render, screen, getByRole } from '@testing-library/react';
import UserSettingsApiKeyForm from './UserSettingsApiKeyForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import * as AuthAPIModule from 'api/auth';
import * as copyTextToClipboardModule from 'utils/copyTextToClipboard';

describe('<UserSettingsApiKeyForm />', () => {
  // API key doesn't update with API calls, because apiKey prop is passed from parent component
  // and not changed inside ApiKeyForm, therefore only method calls can be tested here

  it('renders API key textbox value with buttons to generate new or delete current key', async () => {
    const postApiKeySpy = jest.spyOn(AuthAPIModule, 'postApiKey').mockResolvedValue({ api_key: 'generated_api_key' });
    render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <UserSettingsApiKeyForm apiKey={null} />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );

    const textboxArea = screen.getByRole('textbox');
    expect(textboxArea).toHaveValue('');
    expect(textboxArea).toHaveAttribute('readonly');
    expect(textboxArea.parentElement).toHaveTextContent('API key');

    const generateKeyButton = screen.getByRole('button', {
      name: dictionary['en']['user_settings_api_key_btn_generate']
    });
    const deleteKeyButton = screen.getByRole('button', { name: dictionary['en']['user_settings_api_key_btn_remove'] });
    expect(deleteKeyButton).toHaveAttribute('disabled'); // since theres no API key to delete

    await userEvent.click(generateKeyButton);
    expect(postApiKeySpy).toHaveBeenCalled();
    expect(textboxArea).toHaveValue(''); // no inner state update
  });

  it('requires confirmation to either change or delete current key', async () => {
    const apiKey = 'test_api_key';
    const generatedApiKey = 'test_generated_api_key';
    const postApiKeySpy = jest.spyOn(AuthAPIModule, 'postApiKey').mockResolvedValue({ api_key: generatedApiKey });
    const deleteApiKeySpy = jest.spyOn(AuthAPIModule, 'deleteApiKey').mockResolvedValue({});
    const copyTextToClipboardSpy = jest.spyOn(copyTextToClipboardModule, 'copyTextToClipboard');

    render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper>
          <UserSettingsApiKeyForm apiKey={apiKey} />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );

    const textboxArea = screen.getByRole('textbox');
    expect(textboxArea).toHaveValue(apiKey);
    expect(textboxArea).toHaveAttribute('readonly');
    expect(textboxArea.parentElement).toHaveTextContent('API key');

    // when input contains text, it becomes clickable and allows to copy contents to clipboard;
    await userEvent.setup({ delay: null }).click(textboxArea); // since working with setTimeout component
    expect(copyTextToClipboardSpy).toHaveBeenCalledWith(apiKey, expect.any(Function));
    expect(screen.getByText(dictionary['en']['user_settings_api_key_copied_to_clipboard'])).toBeInTheDocument();

    const generateKeyButton = screen.getByRole('button', {
      name: dictionary['en']['user_settings_api_key_btn_generate']
    });
    const deleteKeyButton = screen.getByRole('button', { name: dictionary['en']['user_settings_api_key_btn_remove'] });

    expect(deleteKeyButton).not.toHaveAttribute('disabled'); // since there is API key to delete

    await userEvent.click(generateKeyButton); // request to generate new key over existing requires confirmation from modal
    expect(postApiKeySpy).not.toHaveBeenCalled(); // no confirmation yet
    let modalElement = screen.getByRole('dialog');
    expect(modalElement).toHaveTextContent(
      'This will irretrievably delete the existing API key. Are you sure you want to do that?'
    );

    let cancelButton = getByRole(modalElement, 'button', {
      name: dictionary['en']['user_settings_api_key_confirmation_cancel_btn']
    });
    await userEvent.click(cancelButton); // cancelation of generating
    expect(postApiKeySpy).not.toHaveBeenCalled();
    expect(modalElement).not.toBeInTheDocument(); // modal hides upon decision

    await userEvent.click(generateKeyButton);
    modalElement = screen.getByRole('dialog'); // element deleted from document has to be retrieved once more
    expect(modalElement).toBeInTheDocument();
    let confirmButton = getByRole(modalElement, 'button', {
      name: dictionary['en']['user_settings_api_key_confirmation_confirm_btn']
    });
    await userEvent.click(confirmButton); // confirmation of generating
    expect(postApiKeySpy).toHaveBeenCalled(); // finally received confirmation
    expect(modalElement).not.toBeInTheDocument();

    await userEvent.click(deleteKeyButton);
    modalElement = screen.getByRole('dialog'); // element deleted from document has to be retrieved once more
    cancelButton = getByRole(modalElement, 'button', {
      name: dictionary['en']['user_settings_api_key_confirmation_cancel_btn']
    });
    expect(modalElement).toBeInTheDocument();
    await userEvent.click(cancelButton); // cancelation of deleting
    expect(deleteApiKeySpy).not.toHaveBeenCalled(); // no confirmation yet
    expect(modalElement).not.toBeInTheDocument();

    await userEvent.click(deleteKeyButton);
    modalElement = screen.getByRole('dialog'); // element deleted from document has to be retrieved once more
    confirmButton = getByRole(modalElement, 'button', {
      name: dictionary['en']['user_settings_api_key_confirmation_confirm_btn']
    });
    expect(modalElement).toBeInTheDocument();
    await userEvent.click(confirmButton); // confirmation of deleting
    expect(deleteApiKeySpy).toHaveBeenCalled(); // no confirmation yet
    expect(modalElement).not.toBeInTheDocument();
  });
});
