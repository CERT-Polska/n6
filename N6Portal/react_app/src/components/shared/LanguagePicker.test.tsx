import { render, screen } from '@testing-library/react';
import LanguagePicker from './LanguagePicker';
import { LanguageContext } from 'context/LanguageProvider';
import { dictionary } from 'dictionary';
import userEvent from '@testing-library/user-event';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';

describe('<LanguagePicker />', () => {
  it.each([
    { mode: 'text', fullDictName: true },
    { mode: 'text', fullDictName: false },
    { mode: 'icon', fullDictName: true },
    { mode: 'icon', fullDictName: false }
  ])('renders buttons to handle changes of locale', async ({ mode, fullDictName }) => {
    const buttonClassname = 'test button classname';
    const handleChangeLang = jest.fn();

    const { container } = render(
      <LanguageProviderTestWrapper locale="en">
        <LanguageContext.Provider value={{ handleChangeLang }}>
          <LanguagePicker
            mode={mode as 'text' | 'icon'}
            fullDictName={fullDictName}
            buttonClassName={buttonClassname}
          />
        </LanguageContext.Provider>
      </LanguageProviderTestWrapper>
    );

    const buttons = screen.getAllByRole('button', { name: dictionary['en']['language_picker_aria_label'] });
    expect(buttons).toHaveLength(2);

    expect(buttons[0]).toHaveClass(`language-picker-button p-0 ${buttonClassname} selected`); // english icon comes first
    expect(buttons[0]).toHaveClass(`language-picker-button p-0 ${buttonClassname}`); // english icon comes first

    if (mode === 'icon') {
      const enIcon = container.querySelector('svg-en-icon-mock');
      const plIcon = container.querySelector('svg-pl-icon-mock');
      expect(buttons[0].firstChild).toBe(enIcon);
      expect(buttons[1].firstChild).toBe(plIcon);
    } else {
      expect(buttons[0]).toHaveTextContent(fullDictName ? 'English' : 'EN');
      expect(buttons[1]).toHaveTextContent(fullDictName ? 'Polish' : 'PL');
    }

    await userEvent.click(buttons[0]);
    expect(handleChangeLang).toHaveBeenLastCalledWith('en');
    await userEvent.click(buttons[1]);
    expect(handleChangeLang).toHaveBeenLastCalledWith('pl');
  });
});
