/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import Footer from './Footer';
import { useLocation } from 'react-router-dom';
import routeList from 'routes/routeList';
import { LanguageProvider } from 'context/LanguageProvider';
import * as LanguagePickerModule from 'components/shared/LanguagePicker';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn()
}));
const useLocationMock = useLocation as jest.Mock;

describe('<Footer />', () => {
  it.each([{ pathname: routeList.login }, { pathname: routeList.forgotPassword }])(
    'renders footer with LanguagePicker component \
        in "/" and "/password-reset" endpoint layouts',
    ({ pathname }) => {
      useLocationMock.mockReturnValue({ pathname: pathname });
      const LanguagePickerSpy = jest.spyOn(LanguagePickerModule, 'default');

      const { container } = render(
        <LanguageProvider>
          <Footer />
        </LanguageProvider>
      );

      const footer = screen.getByRole('contentinfo');
      expect(footer).toBeInTheDocument();
      expect(footer).toHaveClass('page-footer d-flex justify-content-center align-items-center');

      expect(container.querySelectorAll('button').length).toBe(2); // two buttons

      const englishButton = screen.getByText('English');
      expect(englishButton).toHaveClass('language-picker-button p-0 m-2 selected'); //english by default

      const polishButton = screen.getByText('Polish');
      expect(polishButton).toHaveClass('language-picker-button p-0 m-2');

      expect(LanguagePickerSpy).toHaveBeenCalledWith(
        {
          mode: 'text',
          fullDictName: true,
          buttonClassName: 'm-2'
        },
        {}
      );
    }
  );

  it('returns nothing in any other path than provided previously', () => {
    useLocationMock.mockReturnValue({ pathname: '/random-path' });
    const { container } = render(
      <LanguageProvider>
        <Footer />
      </LanguageProvider>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
