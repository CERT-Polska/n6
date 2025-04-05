import { render, screen } from '@testing-library/react';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import SignUpStepOne from './SignUpStepOne';
import { dictionary, signup_terms } from 'dictionary';
import * as ReactMarkdownModule from 'react-markdown';
import userEvent from '@testing-library/user-event';

describe('<SignUpStepOne', () => {
  it.each([{ locale: 'en' as 'en' | 'pl' }, { locale: 'pl' as 'en' | 'pl' }])(
    'renders ToS in given language, checkbox to agree to them and action buttons',
    async ({ locale }) => {
      const ReactMarkdownSpy = jest.spyOn(ReactMarkdownModule, 'default');
      const changeStepMock = jest.fn();
      const TOSContent = process.env.REACT_APP_TOS
        ? JSON.parse(process.env.REACT_APP_TOS)[locale]['terms']
        : signup_terms[locale]['content'];
      render(
        <LanguageProviderTestWrapper locale={locale}>
          <SignUpStepOne changeStep={changeStepMock} changeTosVersions={jest.fn()} />
        </LanguageProviderTestWrapper>
      );
      const checkboxElement = screen.getByRole('checkbox');
      expect(screen.getByText(dictionary[locale]['signup_terms_checkbox_label'])).toBeInTheDocument();
      expect(ReactMarkdownSpy).toHaveBeenNthCalledWith(1, { children: TOSContent }, {});
      expect(checkboxElement).not.toBeChecked();
      const nextButton = screen.getByRole('button', { name: dictionary[locale]['signup_btn_next'] });
      await userEvent.click(nextButton);
      expect(changeStepMock).not.toHaveBeenCalled(); // terms have not been agreed to
      await userEvent.click(checkboxElement);
      expect(checkboxElement).toBeChecked();
      await userEvent.click(nextButton);
      expect(changeStepMock).toHaveBeenCalledWith(2);
    }
  );
});
