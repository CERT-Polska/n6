/**
 * @jest-environment jsdom
 */

import React, { PropsWithChildren } from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import { IntlProvider } from 'react-intl';
import userEvent from '@testing-library/user-event';
import CustomFieldArray, { IProps } from 'components/shared/CustomFieldArray';
import { TEditSettingsForm } from 'components/pages/editSettings/EditSettingsForm';
import { validateDomainNotRequired } from 'components/forms/validation/validationSchema';
import { dictionary } from 'dictionary';

// Mock the SVG imports
jest.mock('images/delete.svg', () => ({
  ReactComponent: () => <div data-testid="trash-icon" />
}));
jest.mock('images/plus.svg', () => ({
  ReactComponent: () => <div data-testid="plus-icon" />
}));
jest.mock('images/restore.svg', () => ({
  ReactComponent: () => <div data-testid="restore-icon" />
}));

interface WrapperProps extends PropsWithChildren {
  defaultFormValues?: Partial<TEditSettingsForm>;
  componentProps: IProps;
}

const Wrapper: React.FC<WrapperProps> = ({ children, defaultFormValues = {}, componentProps }) => {
  // If updatedValues exists, use only those values, otherwise use defaultValues
  const mergedValues = componentProps.updatedValues || componentProps.defaultValues;

  const initialValues = {
    [componentProps.name]: mergedValues,
    ...defaultFormValues
  };

  const methods = useForm<TEditSettingsForm>({
    mode: 'onBlur',
    defaultValues: initialValues
  });

  return (
    <IntlProvider messages={dictionary['en']} locale="en">
      <FormProvider {...methods}>{children}</FormProvider>
    </IntlProvider>
  );
};

const defaultProps: IProps = {
  name: 'fqdns',
  label: 'FQDN',
  defaultValues: [{ value: 'domain1.com' }, { value: 'domain2.com' }],
  validate: validateDomainNotRequired,
  header: 'FQDNs',
  updatedValues: undefined
};

const renderWithWrapper = (props: IProps = defaultProps) => {
  return render(
    <Wrapper componentProps={props}>
      <CustomFieldArray {...props} />
    </Wrapper>
  );
};

const getEntryFieldElements = () => {
  const entryField = screen.getByTestId('fqdns-entry-field');
  return {
    entryField,
    input: within(entryField).getByRole('textbox'),
    addButton: within(entryField).getByLabelText('fqdns-add-button')
  };
};

const typeAndAddDomain = async (domain: string) => {
  const { input, addButton } = getEntryFieldElements();
  await userEvent.type(input, domain);
  await userEvent.click(addButton);
};

describe('CustomFieldArray', () => {
  describe('Rendering', () => {
    it('renders header and tooltip correctly', () => {
      const tooltipText = 'Test tooltip';
      const propsWithTooltip = { ...defaultProps, tooltip: <div>{tooltipText}</div> };
      renderWithWrapper(propsWithTooltip);

      expect(screen.getByText('FQDNs')).toBeInTheDocument();
      expect(screen.getByText(tooltipText)).toBeInTheDocument();
    });

    it('renders initial fields with correct attributes', () => {
      renderWithWrapper();
      const fields = screen.getAllByTestId(/fqdns-field-/i);

      fields.forEach((field, index) => {
        const input = within(field).getByRole('textbox');
        const deleteButton = within(field).getByLabelText(`fqdns-remove-button-${index}`);
        expect(within(field).getByTestId('trash-icon')).toBeInTheDocument();

        expect(input).toBeDisabled();
        expect(deleteButton).toBeEnabled();
        expect(within(field).getByLabelText('FQDN')).toBeInTheDocument();
      });
    });

    it('renders entry field with correct attributes', () => {
      renderWithWrapper();
      const entryField = screen.getByTestId('fqdns-entry-field');

      const input = within(entryField).getByRole('textbox');
      const addButton = within(entryField).getByLabelText('fqdns-add-button');

      expect(input).toHaveValue('');
      expect(input).toBeEnabled();
      expect(addButton).toBeEnabled();
    });
  });

  describe('Field Addition', () => {
    it('adds new field with valid domain and clears entry field', async () => {
      renderWithWrapper();

      await typeAndAddDomain('newdomain.com');

      const fields = await waitFor(() => {
        const fields = screen.getAllByTestId(/fqdns-field-/i);
        expect(fields).toHaveLength(3);
        return fields;
      });

      await waitFor(() => {
        const newField = within(fields[2]).getByRole('textbox');
        expect(newField).toHaveValue('newdomain.com');
      });

      expect(getEntryFieldElements().input).toHaveValue('');
    });

    it('validates domain format before adding', async () => {
      renderWithWrapper();

      await typeAndAddDomain('invalid-domain.');

      const fields = screen.getAllByTestId(/fqdns-field-/i);
      expect(fields).toHaveLength(2); // Should not add invalid domain
    });
  });

  describe('Field Removal and Restoration', () => {
    it('removes field and shows it in restore section with correct attributes', async () => {
      renderWithWrapper();

      const removeButton = screen.getByLabelText('fqdns-remove-button-0');

      await userEvent.click(removeButton);

      const elements = await waitFor(() => {
        const restoreField = screen.getByTestId('fqdns-restore-field-0');
        const restoreInput = within(restoreField).getByRole('textbox');
        const restoreButton = within(restoreField).getByLabelText('fqdns-restore-button-0');

        return [restoreField, restoreInput, restoreButton];
      });

      const [restoreField, restoreInput, restoreButton] = elements;

      expect(restoreInput).toHaveValue('domain1.com');
      expect(restoreInput).toBeDisabled();
      expect(restoreButton).toBeEnabled();
      expect(within(restoreField).getByTestId('restore-icon')).toBeInTheDocument();
    });

    it('restores field to original position', async () => {
      renderWithWrapper();

      // Remove first field
      await userEvent.click(screen.getByLabelText('fqdns-remove-button-0'));

      // Restore it back
      const restoreField = await screen.findByTestId('fqdns-restore-field-0');
      await userEvent.click(within(restoreField).getByLabelText('fqdns-restore-button-0'));

      const fields = await waitFor(() => {
        const fields = screen.getAllByTestId(/fqdns-field-/i);
        expect(fields).toHaveLength(2);
        return fields;
      });

      expect(within(fields[0]).getByRole('textbox')).toHaveValue('domain1.com');
    });
  });

  describe('Updated Values Handling - pending changes', () => {
    it('handles updated values IUpdateInfo correctly showing removed fields in restore section', () => {
      const propsWithUpdatedValues = {
        ...defaultProps,
        updatedValues: [{ value: 'domain1.com' }],
        disabled: true
      };

      renderWithWrapper(propsWithUpdatedValues);

      // Check active fields
      const fields = screen.getAllByTestId(/fqdns-field-/i);
      expect(fields).toHaveLength(1);

      fields.forEach((field, index) => {
        const input = within(field).getByRole('textbox');
        const deleteButton = within(field).getByLabelText(`fqdns-remove-button-${index}`);

        expect(input).toBeDisabled();
        expect(deleteButton).toBeDisabled();
      });

      // Check restore fields
      const restoreField = screen.getByTestId('fqdns-restore-field-0');
      expect(within(restoreField).getByRole('textbox')).toHaveValue('domain2.com');
      expect(within(restoreField).getByLabelText('fqdns-restore-button-0')).toBeDisabled();
    });
  });

  describe('Disabled State', () => {
    it('disables all interactive elements when disabled prop is true', () => {
      const disabledProps = {
        ...defaultProps,
        disabled: true
      };

      renderWithWrapper(disabledProps);

      // Check entry field
      const entryField = screen.getByTestId('fqdns-entry-field');
      expect(within(entryField).getByRole('textbox')).toBeDisabled();
      expect(within(entryField).getByLabelText('fqdns-add-button')).toBeDisabled();

      // Check existing fields
      const fields = screen.getAllByTestId(/fqdns-field-/i);
      fields.forEach((field, index) => {
        expect(within(field).getByRole('textbox')).toBeDisabled();
        expect(within(field).getByLabelText(`fqdns-remove-button-${index}`)).toBeDisabled();
      });
    });
  });
});
