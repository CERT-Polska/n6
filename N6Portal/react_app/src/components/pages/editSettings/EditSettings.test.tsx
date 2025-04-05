import { render, screen } from '@testing-library/react';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { useOrgConfig } from 'api/orgConfig';
import EditSettings from 'components/pages/editSettings/EditSettings';
import { IOrgConfig } from 'api/orgConfig/types';

// Mock dependencies
jest.mock('api/orgConfig');
jest.mock('components/loading/ApiLoader', () => ({
  __esModule: true,
  default: ({ children, status, error }: { children: React.ReactNode; status: string; error: Error | null }) => (
    <div>
      {status === 'loading' && <div data-testid="loader-wrapper">Loading...</div>}
      {status === 'error' && error && <div data-testid="error-message">{error.message}</div>}
      {status === 'success' && children}
    </div>
  )
}));

// Types
type Locale = 'en' | 'pl';

describe('EditSettings', () => {
  const mockOrgConfig = useOrgConfig as jest.MockedFunction<typeof useOrgConfig>;

  const renderComponent = (lang: Locale = 'en') => {
    return render(
      <QueryClientProviderTestWrapper>
        <LanguageProviderTestWrapper locale={lang}>
          <EditSettings />
        </LanguageProviderTestWrapper>
      </QueryClientProviderTestWrapper>
    );
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('shows loading state when fetching data', () => {
    mockOrgConfig.mockReturnValue({
      data: undefined,
      status: 'loading',
      error: null,
      isLoading: true,
      isError: false,
      isSuccess: false,
      refetch: jest.fn()
    } as any);

    renderComponent();
    expect(screen.getByTestId('loader-wrapper')).toBeInTheDocument();
    expect(screen.queryByTestId('error-message')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('test-org')).not.toBeInTheDocument();
  });

  it('shows error message when fetch fails', () => {
    const error = new Error('Failed to fetch');
    mockOrgConfig.mockReturnValue({
      data: undefined,
      status: 'error',
      error,
      isLoading: false,
      isError: true,
      isSuccess: false,
      refetch: jest.fn()
    } as any);

    renderComponent();
    expect(screen.getByTestId('error-message')).toBeInTheDocument();
    expect(screen.getByText('Failed to fetch')).toBeInTheDocument();
    expect(screen.queryByTestId('loader-wrapper')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('test-org')).not.toBeInTheDocument();
  });

  it('renders EditSettingsForm when data is loaded successfully', () => {
    const mockData: IOrgConfig = {
      org_id: 'test-org',
      actual_name: 'Test Org',
      org_user_logins: ['user1@test.com'],
      asns: [1234],
      fqdns: ['domain1.com'],
      ip_networks: ['192.168.1.0/24'],
      notification_enabled: true,
      notification_language: 'EN',
      notification_emails: ['notify@test.com'],
      notification_times: ['10:00'],
      post_accepted: null,
      update_info: null
    };

    mockOrgConfig.mockReturnValue({
      data: mockData,
      status: 'success',
      error: null,
      isLoading: false,
      isError: false,
      isSuccess: true,
      refetch: jest.fn()
    } as any);

    renderComponent();
    expect(screen.getByDisplayValue('test-org')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test Org')).toBeInTheDocument();
    expect(screen.queryByTestId('loader-wrapper')).not.toBeInTheDocument();
    expect(screen.queryByTestId('error-message')).not.toBeInTheDocument();
  });

  it('handles null data gracefully', () => {
    mockOrgConfig.mockReturnValue({
      data: null,
      status: 'success',
      error: null,
      isLoading: false,
      isError: false,
      isSuccess: true,
      refetch: jest.fn()
    } as any);

    renderComponent();
    expect(screen.queryByDisplayValue('test-org')).not.toBeInTheDocument();
    expect(screen.queryByTestId('loader-wrapper')).not.toBeInTheDocument();
    expect(screen.queryByTestId('error-message')).not.toBeInTheDocument();
  });
});
