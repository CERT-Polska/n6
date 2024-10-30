/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AgreementsSettingsForm from './AgreementsSettingsForm';
import { QueryClient, QueryClientProvider } from 'react-query';
import { dictionary } from 'dictionary';
import { IAgreement } from 'api/services/agreements';
import { BrowserRouter } from 'react-router-dom';
import { IntlProvider } from 'react-intl';
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
          <QueryClientProvider client={new QueryClient()}>
            <IntlProvider locale={locale} messages={dictionary[locale as keyof typeof dictionary]}>
              <AgreementsSettingsForm agreementsList={agreementsList} orgAgreements={orgAgreements} />
            </IntlProvider>
          </QueryClientProvider>
        </BrowserRouter>
      );

      expect(postOrgAgreementsSpy).not.toHaveBeenCalled();

      expect(container.firstChild).toHaveClass('agreements-settings-form-wrapper font-bigger');
      expect(container.firstChild?.firstChild).toHaveRole('heading');
      expect(container.firstChild?.firstChild).toHaveTextContent(
        dictionary[locale as keyof typeof dictionary]['agreements_settings_title']
      );

      expect(container.firstChild?.childNodes).toHaveLength(agreementsList.length + 1);

      agreementsList.forEach((agreement, index) => {
        const agreementComponent = container.firstChild?.childNodes[index + 1];
        expect(agreementComponent).toHaveClass('form-checkbox-wrapper custom-checkbox-input');
        expect(agreementComponent).toHaveTextContent(agreement[locale as keyof typeof dictionary]);

        const inputElement = agreementComponent?.firstChild;
        expect(inputElement).toHaveRole('checkbox');
        expect(inputElement).toHaveClass('form-checkbox-input form-check-input');
        if (orgAgreements.includes(agreement.label)) {
          expect(inputElement).toBeChecked();
        } else {
          expect(inputElement).not.toBeChecked();
        }

        const spanElement = agreementComponent?.childNodes[1];
        expect(spanElement).toHaveClass('custom-checkbox');

        const labelElement = agreementComponent?.childNodes[2];
        expect(labelElement).toHaveClass('form-checkbox-label form-check-label');
        expect(labelElement).toHaveAttribute('for', `checkbox-${agreement.label}`);
        expect(labelElement).toHaveTextContent(agreement[locale as keyof typeof dictionary]);

        const possibleUrl = agreement[`url_${locale}` as keyof IAgreement];
        if (possibleUrl) {
          const linkElement = labelElement?.childNodes[1]; // after text content
          expect(linkElement).toHaveRole('link');
          expect(linkElement).toHaveAttribute('href', possibleUrl);
          expect(linkElement).toHaveAttribute('target', '_blank');
          expect(linkElement).toHaveTextContent(dictionary[locale as keyof typeof dictionary]['agreements_see_more']);
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
