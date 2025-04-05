import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgreementsSettingsForm from './AgreementsSettingsForm';
import { LanguageProviderTestWrapper, QueryClientProviderTestWrapper } from 'utils/testWrappers';
import { dictionary } from 'dictionary';
import { IAgreement } from 'api/services/agreements';
import { BrowserRouter } from 'react-router-dom';
import * as postOrgAgreementsModule from 'api/services/agreements';
import { customAxios } from 'api';

describe('<AgreementsSettingsForm />', () => {
  afterEach(() => {
    cleanup();
    jest.clearAllMocks();
    jest.resetAllMocks();
    jest.restoreAllMocks();
  });

  it.each([{ locale: 'en' }, { locale: 'pl' }])(
    'renders a labeled checkbox for every given agreement with properties depending on orgAgreements. \
    It calls for /org_agreements POST endpoint with every checkbox change.',
    async ({ locale }) => {
      const agreementsList: IAgreement[] = [
        {
          label: 'first_label',
          pl: 'first_pl',
          en: 'first_en',
          default_consent: false,
          url_en: '',
          url_pl: 'https://example.com'
        },
        {
          label: 'second_label',
          pl: 'second_pl',
          en: 'second_en',
          default_consent: true,
          url_en: 'example.com'
        }
      ];

      // NOTE: org_agreements functions as list of existing agreements labels and
      // this component in itself has no validation on this part, since it's on backend side
      // to provide valid data to this component
      const orgAgreements: string[] = ['first_label'];

      const postOrgAgreementsSpy = jest.spyOn(postOrgAgreementsModule, 'postOrgAgreements');
      jest.spyOn(customAxios, 'post').mockImplementation((data) => Promise.resolve({ data: data }));

      const { container } = render(
        <BrowserRouter>
          <QueryClientProviderTestWrapper>
            <LanguageProviderTestWrapper locale={locale as 'en' | 'pl'}>
              <AgreementsSettingsForm agreementsList={agreementsList} orgAgreements={orgAgreements} />
            </LanguageProviderTestWrapper>
          </QueryClientProviderTestWrapper>
        </BrowserRouter>
      );

      expect(postOrgAgreementsSpy).not.toHaveBeenCalled();
      expect(screen.getByRole('heading')).toHaveTextContent(
        locale === 'en' ? 'Edit organization agreements' : 'Edytuj ustawienia zgód organizacji'
      );

      expect(container.firstChild?.childNodes).toHaveLength(agreementsList.length + 1);

      agreementsList.forEach((agreement, index) => {
        const agreementComponent = container.firstChild?.childNodes[index + 1];
        expect(agreementComponent).toHaveTextContent(agreement[locale as keyof typeof dictionary]);

        const inputElement = agreementComponent?.firstChild;
        expect(inputElement).toHaveRole('checkbox');
        if (orgAgreements.includes(agreement.label)) {
          expect(inputElement).toBeChecked();
        } else {
          expect(inputElement).not.toBeChecked();
        }

        const labelElement = agreementComponent?.childNodes[2];
        expect(labelElement).toHaveAttribute('for', `checkbox-${agreement.label}`);
        expect(labelElement).toHaveTextContent(agreement[locale as keyof typeof dictionary]);

        const possibleUrl = agreement[`url_${locale}` as keyof IAgreement];
        if (possibleUrl) {
          const linkElement = labelElement?.childNodes[1]; // after text content
          expect(linkElement).toHaveRole('link');
          expect(linkElement).toHaveAttribute('href', possibleUrl);
          expect(linkElement).toHaveAttribute('target', '_blank');
          expect(linkElement).toHaveTextContent(locale === 'en' ? 'See more' : 'Zobacz więcej');
        }
      });

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes).toHaveLength(agreementsList.length);
      expect(checkboxes[0]).toBeChecked();
      expect(checkboxes[1]).not.toBeChecked();

      await userEvent.click(checkboxes[0]);
      expect(checkboxes[0]).not.toBeChecked();
      expect(checkboxes[1]).not.toBeChecked();
      expect(postOrgAgreementsSpy).toHaveBeenLastCalledWith([]);

      await userEvent.click(checkboxes[1]);
      expect(checkboxes[0]).not.toBeChecked();
      expect(checkboxes[1]).toBeChecked();
      expect(postOrgAgreementsSpy).toHaveBeenLastCalledWith(['second_label']);

      await userEvent.click(checkboxes[0]);
      expect(checkboxes[0]).toBeChecked();
      expect(checkboxes[1]).toBeChecked();
      expect(postOrgAgreementsSpy).toHaveBeenLastCalledWith(['second_label', 'first_label']);
    }
  );
});
