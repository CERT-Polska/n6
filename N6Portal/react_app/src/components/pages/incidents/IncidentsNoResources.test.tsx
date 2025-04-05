import { render, screen } from '@testing-library/react';
import IncidentsNoResources from './IncidentsNoResources';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';

describe('<IncidentsNoResources />', () => {
  it('renders message about lack of incidents and according icon', () => {
    const { container } = render(
      <LanguageProviderTestWrapper>
        <IncidentsNoResources />
      </LanguageProviderTestWrapper>
    );
    expect(container.querySelector('svg-no-resources-mock')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('No resources available');
  });
});
