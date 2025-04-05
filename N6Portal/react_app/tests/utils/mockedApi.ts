import { Page } from '@playwright/test';
import { AvailableResource, MockedUser } from './mockedUsers';

const mockedEvents = {
  1: {
    source: 'source.channel',
    confidence: 'medium',
    modified: '2016-07-05T22:22:33Z',
    sport: 1000,
    address: [
      {
        cc: 'TT',
        ip: '1.1.1.1',
        asn: 1000
      },
      {
        cc: 'TT',
        ip: '2.2.2.2'
      }
    ],
    proto: 'tcp',
    rid: '5678b8dde1b9c2d362684e942dd4ea01',
    adip: 'x.x.x.82',
    fqdn: 'testdomain.com',
    category: 'cnc',
    sha1: 'a3a3782bfc7aa9c8f0ad63e5e54a5bdc04a49a5d',
    time: '2015-06-05T22:22:33Z',
    ignored: false,
    client: ['client.com'],
    dip: '3.3.3.3',
    dport: 1000,
    url: 'http://testdomain.com/internal',
    id: 'a3a3384e2707a865c24a3ab3803f9f97',
    restriction: 'internal'
  },
  2: {
    source: 'source2.channel2',
    confidence: 'medium2',
    modified: '2017-07-05T22:22:33Z',
    name: 'virut',
    sport: 2000,
    address: [
      {
        cc: 'TT',
        ip: '1.1.1.1',
        asn: 2000
      },
      {
        cc: 'TT',
        ip: '2.2.2.2'
      }
    ],
    proto: 'tcp',
    rid: '1238b8dde1b9c2d362684e942dd4ea01',
    adip: 'x.x.x.83',
    fqdn: 'test2domain.com',
    category: 'bot',
    sha1: '1233782bfc7aa9c8f0ad63e5e54a5bdc04a49a5d',
    time: '2016-06-05T22:22:33Z',
    ignored: false,
    client: ['client2.com'],
    dip: '4.4.4.4',
    dport: 2000,
    url: 'http://test2domain.com/internal',
    id: '1233384e2707a865c24a3ab3803f9f97',
    restriction: 'internal'
  }
};
export const MFA_CONFIG_RESPONSE = {
  secret_key: 'secretKey',
  secret_key_qr_code_url:
    'otpauth://totp/An%20example%20%2An6%2A%20Portal:user%40example.com?secret=secretKey&issuer=An%20example%20%2An6%2A%20Portal'
};

export const MOCKED_SETUP_MFA_RESPONSE = {
  token: 'token',
  mfa_config: MFA_CONFIG_RESPONSE
};

export const MOCKED_MFA_CONFIRM_RESPONSE = {
  mfa_code: '123456',
  token: 'token'
};

export class MockedApi {
  private static readonly hostname = 'https://localhost';
  private static readonly defaultLimit = 1000;
  private static readonly defaultStartDate = '2000-12-01T00:00:00.000Z';

  /**
   * Mocks an API route for the specified path and responds with the given response body.
   * @param page - The Playwright page instance.
   * @param routePath - The path of the API route to mock.
   * @param response_body - The body of the response to return when the route is called.
   * @param httpStatus - The HTTP status code to return (default is 200).
   */
  static mockApiRoute = async (page: Page, routePath: string, response_body: object | undefined, httpStatus = 200) => {
    await page.route(routePath, async (route) => {
      const response = await route.fetch();
      await route.fulfill({ status: httpStatus ?? response.status(), json: response_body });
    });
  };

  /**
   * Mocks the PDF download endpoint for knowledge base articles
   * @param page Playwright page
   * @param articleId Article ID
   * @param language Language code ('en' or 'pl')
   * @param success Whether the download should succeed or fail
   */
  static async mockPdfDownload(page: Page, articleId: string, language: string, success = true) {
    if (success) {
      // Mock successful PDF download
      await page.route(`/api/knowledge_base/articles/${articleId}/${language}/pdf`, async (route) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/pdf',
          body: Buffer.from('PDF content for testing')
        });
      });
    } else {
      // Mock failed PDF download
      await page.route(`/api/knowledge_base/articles/${articleId}/${language}/pdf`, async (route) => {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Failed to generate PDF' })
        });
      });
    }
  }

  /**
   * Builds the incident search URL for the specified service with optional parameters.
   * @param service - The service for which to build the URL.
   * @param options - Optional parameters for the URL.
   * @param options.dateTime - The date and time to filter incidents (default is the default start date).
   * @param options.limit - The maximum number of incidents to return (default is 1000).
   * @param options.filterQuery - Additional query parameters to filter the results.
   * @returns The constructed URL as a string.
   */
  static buildIncidentSearchUrl(
    service: AvailableResource[number],
    options: {
      dateTime?: Date;
      limit?: number;
      filterQuery?: string;
    } = {}
  ): string {
    const { dateTime = new Date(this.defaultStartDate), limit = this.defaultLimit, filterQuery = '' } = options;

    return `${this.hostname}/api${service}.json?${filterQuery}time.min=${dateTime.toISOString()}&opt.limit=${limit}`;
  }

  /**
   * Mocks the logout API route.
   * @param page - The Playwright page instance.
   */
  static async getLogout(page: Page) {
    await this.mockApiRoute(page, '/api/logout', {});
  }

  /**
   * Mocks the API route to get information about a not authenticated user.
   * @param page - The Playwright page instance.
   */
  static async getNotAuthenticatedUserInfo(page: Page) {
    await this.mockApiRoute(page, '/api/info', { authenticated: false });
  }

  /**
   * Mocks the API route to get user information.
   * @param page - The Playwright page instance.
   * @param user - The mocked user object containing user details.
   */
  static async getUserInfo(page: Page, user: MockedUser) {
    const userInfo = {
      authenticated: true,
      org_id: 'cert.pl',
      org_actual_name: 'CERT Polska',
      available_resources: user.availableResources,
      full_access: user.fullAccess,
      api_key_auth_enabled: user.api_key_auth_enabled,
      knowledge_base_enabled: user.knowledgeBaseEnabled
    };
    await this.mockApiRoute(page, '/api/info', userInfo);
  }

  /**
   * Mocks the API route to get a single incident event for the specified service.
   * @param page - The Playwright page instance.
   * @param service - The service for which to get the incident event.
   */
  static async getIncidentEvent(page: Page, service: AvailableResource[number]) {
    const url = this.buildIncidentSearchUrl(service);
    await this.mockApiRoute(page, url, [mockedEvents[1]]);
  }

  /**
   * Mocks the API route to get two incident events for the specified service.
   * @param page - The Playwright page instance.
   * @param service - The service for which to get the incident events.
   */
  static async getTwoIncidentEvents(page: Page, service: AvailableResource[number]) {
    const url = this.buildIncidentSearchUrl(service);
    await this.mockApiRoute(page, url, [mockedEvents[1], mockedEvents[2]]);
  }
}
