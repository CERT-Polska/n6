import ArticleSearchForm from './ArticleSearchForm';
import { render, screen } from '@testing-library/react';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { useLocation } from 'react-router-dom';
import { dictionary } from 'dictionary';
import { searchRegex } from 'components/forms/validation/validationRegexp';

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useLocation: jest.fn()
}));
const useLocationMock = useLocation as jest.Mock;

describe('<ArticleSearchForm />', () => {
  it.each([
    { locationMockValue: '', expectMatchSearchRegex: false },
    { locationMockValue: 'aa', expectMatchSearchRegex: false }, // too short for searchRegex to consider it default value
    { locationMockValue: 'a'.repeat(101), expectMatchSearchRegex: false }, // too long
    { locationMockValue: 'IZ^gI~+3 nANA}y<.M") Qv0^H5LtnXtN];*X>:=9#/yMm2"-[lp)ZP}', expectMatchSearchRegex: true } // characters don't matter, only number of chars
  ])('renders search bar for articles', ({ locationMockValue, expectMatchSearchRegex }) => {
    useLocationMock.mockReturnValue({ search: `q=${locationMockValue}` }); // query param

    const { container } = render(
      <LanguageProviderTestWrapper>
        <ArticleSearchForm />
      </LanguageProviderTestWrapper>
    );

    const textboxElement = screen.getByRole('textbox');
    expect(textboxElement).toHaveAttribute('placeholder', dictionary['en']['knowledge_base_search_placeholder']);
    expect(textboxElement).toHaveAttribute('id', 'input-query');
    if (expectMatchSearchRegex) {
      expect(locationMockValue).toMatch(searchRegex);
      expect(textboxElement).toHaveValue(locationMockValue);
    } else {
      expect(locationMockValue).not.toMatch(searchRegex);
      expect(textboxElement).toHaveValue('');
    }

    const searchIcon = container.querySelector('svg-search-mock') as HTMLElement;
    expect(searchIcon).toBeInTheDocument();
    expect(searchIcon.parentElement).toHaveAttribute('type', 'submit'); // button
  });
});
