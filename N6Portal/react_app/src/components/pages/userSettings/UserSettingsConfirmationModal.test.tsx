import { render, screen } from '@testing-library/react';
import UserSettingsConfirmationModal from './UserSettingsConfirmationModal';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';

describe('<UserSettingsConfirmationModal />', () => {
  it('returns nothing if show param is set to false', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <UserSettingsConfirmationModal show={false} onHide={jest.fn()} />
      </LanguageProviderTestWrapper>
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('returns modal with confirm and cancel buttons and custom actions', async () => {
    const onHideMock = jest.fn();
    const onConfirmMock = jest.fn();
    const { container } = render(
      <LanguageProviderTestWrapper>
        <UserSettingsConfirmationModal show={true} onHide={onHideMock} onConfirm={onConfirmMock} />
      </LanguageProviderTestWrapper>
    );
    expect(container).toBeEmptyDOMElement(); // aria-hidden="true" causes container accesibility API be unable to reach modal contents

    expect(screen.getByText(dictionary['en']['user_settings_api_key_confirmation_title'])).toHaveClass(
      'modal-title h4'
    );
    expect(screen.getByRole('dialog')).toHaveTextContent(
      'This will irretrievably delete the existing API key. Are you sure you want to do that?'
    );

    const cancelButton = screen.getByRole('button', {
      name: dictionary['en']['user_settings_api_key_confirmation_cancel_btn']
    });
    expect(onHideMock).not.toHaveBeenCalled();
    await userEvent.click(cancelButton);
    expect(onHideMock).toHaveBeenCalled();

    const confirmButton = screen.getByRole('button', {
      name: dictionary['en']['user_settings_api_key_confirmation_confirm_btn']
    });
    expect(onConfirmMock).not.toHaveBeenCalled();
    await userEvent.click(confirmButton);
    expect(onConfirmMock).toHaveBeenCalled();
  });

  it('disables buttons if modal is in loading state', () => {
    render(
      <LanguageProviderTestWrapper>
        <UserSettingsConfirmationModal show={true} onHide={jest.fn()} loadingCta={true} />
      </LanguageProviderTestWrapper>
    );

    const cancelButton = screen.getByRole('button', {
      name: dictionary['en']['user_settings_api_key_confirmation_cancel_btn']
    });
    const confirmButton = screen.getByRole('button', { name: '' }); // nameless button since loading
    expect(cancelButton.className).toContain('disabled');
    expect(confirmButton.className).toContain('disabled loading');
  });
});
