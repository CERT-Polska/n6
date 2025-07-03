import { IIpMinMaxSeq, TAvailableResources } from 'api/services/info/types';
import * as reactQueryModule from 'react-query';
import { render, screen, getByRole, getByText } from '@testing-library/react';
import Account from './Account';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';

describe('<Account />', () => {
  it('renders Account page consisting of multiple windows with user account config', () => {
    const cc_seq = ['test_cc', 'test_cc2'];
    const fqdn_seq = ['test_fqdn', 'test_fqdn_2'];
    const url_seq = ['test_url.com', 'test_url2.com'];
    const asn_seq = [1, 2, 3];
    const ip_min_max_seq: IIpMinMaxSeq[] = [
      { min_ip: '0.0.0.0/16', max_ip: '0.0.0.0/32' },
      { min_ip: '1.1.1.1/16', max_ip: '1.1.1.1/32' }
    ];
    const userConfig = {
      available_resources: ['/report/inside', '/search/events'],
      user_id: 'test_user_id',
      org_id: 'test_org_id',
      org_actual_name: 'Test Org Actual Name',
      email_notifications: {
        email_notification_times: ['09:00', '12:00'],
        email_notification_addresses: ['example1@example.com', 'example2@example.com'],
        email_notification_language: 'EN',
        email_notification_business_days_only: true
      },
      inside_criteria: {
        cc_seq: cc_seq,
        fqdn_seq: fqdn_seq,
        url_seq: url_seq,
        asn_seq: asn_seq,
        ip_min_max_seq: ip_min_max_seq
      }
    };

    jest
      .spyOn(reactQueryModule, 'useQuery')
      .mockImplementation(jest.fn().mockReturnValue({ data: userConfig, isLoading: false, isSuccess: true }));

    const { container } = render(
      <LanguageProviderTestWrapper>
        <QueryClientProviderTestWrapper>
          <Account />
        </QueryClientProviderTestWrapper>
      </LanguageProviderTestWrapper>
    );

    expect(screen.getByText('Account information')).toBeInTheDocument();
    const accountPageContainers = container.firstChild?.childNodes[1].firstChild?.childNodes as NodeList;
    expect(accountPageContainers).toHaveLength(3); // user info, email and inside criteria

    const userInfoContainer = accountPageContainers[0] as HTMLElement;
    const organizationInfoContainer = accountPageContainers[1] as HTMLElement;
    const emailInfoContainer = accountPageContainers[2] as HTMLElement;

    expect(getByRole(userInfoContainer, 'heading', { level: 2 })).toHaveTextContent('User');
    expect(getByRole(organizationInfoContainer, 'heading', { level: 2 })).toHaveTextContent('Organization');
    expect(getByRole(emailInfoContainer, 'heading', { level: 2 })).toHaveTextContent('E-mail notification settings');

    const headers = [
      [userInfoContainer, 'User login'],
      [organizationInfoContainer, 'User organization'],
      [organizationInfoContainer, 'Organization actual name'],
      [organizationInfoContainer, 'Available resources'],
      [organizationInfoContainer, 'Inside network criteria'],
      [emailInfoContainer, 'Notification addresses'],
      [emailInfoContainer, 'Notification times'],
      [emailInfoContainer, 'Notification language'],
      [emailInfoContainer, 'Notifications on business days only']
    ];

    // overall headers
    for (const [container, header] of headers) {
      expect(getByText(container as HTMLElement, header as string)).toBeInTheDocument();
    }

    // available resources information content
    userConfig.available_resources.forEach((resource) => {
      expect(
        getByText(organizationInfoContainer, dictionary['en'][`account_resources_${resource as TAvailableResources}`])
      ).toBeInTheDocument();
    });

    // email information content
    userConfig.email_notifications?.email_notification_addresses?.forEach((address) => {
      expect(getByText(emailInfoContainer, address)).toBeInTheDocument();
    });
    userConfig.email_notifications?.email_notification_times?.forEach((time) => {
      expect(getByText(emailInfoContainer, time)).toBeInTheDocument();
    });
    expect(
      getByText(
        emailInfoContainer,
        dictionary['en'][
          userConfig.email_notifications?.email_notification_business_days_only ? 'account_yes' : 'account_no'
        ]
      )
    ).toBeInTheDocument();
    expect(
      getByText(emailInfoContainer, userConfig.email_notifications?.email_notification_language as string)
    ).toBeInTheDocument();

    // inside criteria content
    [cc_seq, fqdn_seq, asn_seq, url_seq].forEach((param) => {
      param.forEach((value) => {
        expect(organizationInfoContainer.textContent).toContain(value.toString());
      });
    });
    ip_min_max_seq.forEach((ip_range) => {
      expect(organizationInfoContainer.textContent).toContain(`${ip_range.min_ip} - ${ip_range.max_ip}`);
    });
  });
});
