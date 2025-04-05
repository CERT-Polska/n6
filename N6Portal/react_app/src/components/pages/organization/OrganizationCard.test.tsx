import { render, screen } from '@testing-library/react';
import OrganizationCard from './OrganizationCard';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
import { TCategory } from 'api/services/globalTypes';
import * as TooltipModule from 'components/shared/Tooltip';

describe('<OrganizationCard />', () => {
  it('renders basic card container with heading, given value and tooltip with data explanation', () => {
    const messageKey: TCategory = 'bots'; // NOTE: only TCategory messageKeys have corresponding headers
    const value = 1111;
    const TooltipSpy = jest.spyOn(TooltipModule, 'default');
    render(
      <LanguageProviderTestWrapper>
        <OrganizationCard messageKey={messageKey} value={value} />
      </LanguageProviderTestWrapper>
    );
    expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('Bot');
    expect(screen.getByText(String(value))).toHaveRole('generic');
    expect(TooltipSpy).toHaveBeenCalledWith(
      {
        className: 'organization-tooltip-button',
        content: 'A computer or other device infected by malware.',
        id: messageKey,
        dataTestId: 'organization-card-tooltip-bots'
      },
      {}
    );
  });
});
