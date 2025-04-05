import { cleanup, render } from '@testing-library/react';
import AgreementsSettings from './AgreementsSettings';
import * as AgreementsSettingsFormModule from './AgreementsSettingsForm';
import { useAgreements, useOrgAgreements } from 'api/services/agreements';

jest.mock('api/services/agreements', () => ({
  ...jest.requireActual('api/services/agreements'),
  useAgreements: jest.fn(),
  useOrgAgreements: jest.fn()
}));
const useAgreementsMock = useAgreements as jest.Mock;
const useOrgAgreementsMock = useOrgAgreements as jest.Mock;

describe('<AgreementsSettings />', () => {
  afterEach(() => cleanup());

  it.each([
    { agreementsData: [], orgData: [] }, // NOTE: empty array is still considered a valid data and renders a component
    { agreementsData: [], orgData: 'test_data' },
    { agreementsData: ['test_data'], orgData: [] },
    { agreementsData: [{ agreements: [{}, {}] }], orgData: [{ agreements: [] }] }
  ])(
    'renders <AgreementsSettingsForm /> component nested in ApiLoaders \
    regarding agreements data and orgAgreements data',
    ({ agreementsData, orgData }) => {
      jest
        .spyOn(AgreementsSettingsFormModule, 'default')
        .mockImplementation(({ agreementsList, orgAgreements }) => (
          <h6 className={`${JSON.stringify(agreementsList)}_${JSON.stringify(orgAgreements)}`} />
        ));

      useAgreementsMock.mockReturnValue({ data: agreementsData, status: 'success', error: 'null' });
      useOrgAgreementsMock.mockReturnValue({ data: orgData, status: 'success', error: 'null' });

      const { container } = render(<AgreementsSettings />);

      expect(container.firstChild).toHaveRole('heading');
      expect(container.firstChild).toHaveClass(`${JSON.stringify(agreementsData)}_${JSON.stringify(orgData)}`);
    }
  );

  // cases regarding ApiLoaders failing are described in ApiLoader.test.tsx test file
});
