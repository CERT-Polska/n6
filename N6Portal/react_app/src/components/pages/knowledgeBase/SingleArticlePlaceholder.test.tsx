import { render, screen } from '@testing-library/react';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import SingleArticlePlaceholder from './SingleArticlePlaceholder';
import { dictionary } from 'dictionary';

describe('<SingleArticlePlaceholder />', () => {
  it.each([{ subtitle: undefined }, { subtitle: 'test subtitle' }])(
    'renders welcome/placeholder article page with default header and subtitle',
    ({ subtitle }) => {
      const { container } = render(
        <LanguageProviderTestWrapper>
          <SingleArticlePlaceholder subtitle={subtitle} />
        </LanguageProviderTestWrapper>
      );
      expect(container.querySelector('svg-kb-book-mock')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Knowledge base');
      expect(screen.getByText(subtitle ? subtitle : dictionary['en']['knowledge_base_default_subtitle'])).toHaveRole(
        'paragraph'
      );
    }
  );
});
