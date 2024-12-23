/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import ErrorPage, { IErrorPageVariantType } from './ErrorPage';
const CustomButtonModule = require('components/shared/CustomButton');

describe('<ErrorPage />', () => {
  it.each([
    { variant: 'errBoundary', mockName: 'svg-api-error-mock' },
    { variant: 'notFound', mockName: 'svg-not-found-icon-mock' },
    { variant: 'noAccess', mockName: 'svg-no-access-icon-mock' }
  ])(
    'renders ErrorPage component with header, \
        subtitle, logo and variant icon',
    ({ variant, mockName }) => {
      const textHeader = 'test header';
      const textSubtitle = 'test subtitle';

      const { container } = render(
        <ErrorPage header={textHeader} subtitle={textSubtitle} variant={variant as IErrorPageVariantType} />
      );

      const headerComponent = screen.getByRole('heading', { level: 1 });
      expect(headerComponent).toBeInTheDocument();
      expect(headerComponent).not.toHaveClass();
      expect(headerComponent).toHaveTextContent(textHeader);

      const subtitleComponent = screen.getByText(textSubtitle);
      expect(subtitleComponent).toBeInTheDocument();
      expect(subtitleComponent).toHaveClass('mb-0 error-page-subtitle');
      expect(subtitleComponent).toHaveRole('paragraph');

      const logoIcon = container.querySelector('svg-logo-n6-mock');
      expect(logoIcon).toBeInTheDocument();

      const variantIcon = container.querySelector(mockName);
      expect(variantIcon).toBeInTheDocument();
    }
  );

  it('renders ErrorPage component with header, \
    subtitle, variant icon but without logo in apiLoader variant', () => {
    const textHeader = 'test header';
    const textSubtitle = 'test subtitle';

    const { container } = render(<ErrorPage header={textHeader} subtitle={textSubtitle} variant={'apiLoader'} />);

    const headerComponent = screen.getByRole('heading', { level: 1 });
    expect(headerComponent).toBeInTheDocument();
    expect(headerComponent).not.toHaveClass();
    expect(headerComponent).toHaveTextContent(textHeader);

    const subtitleComponent = screen.getByText(textSubtitle);
    expect(subtitleComponent).toBeInTheDocument();
    expect(subtitleComponent).toHaveClass('mb-0 error-page-subtitle');
    expect(subtitleComponent).toHaveRole('paragraph');

    const logoIcon = container.querySelector('svg-logo-n6-mock');
    expect(logoIcon).not.toBeInTheDocument();

    const variantIcon = container.querySelector('svg-api-error-mock');
    expect(variantIcon).toBeInTheDocument();
  });

  it('calls for <CustomButton /> whenever buttonText is provided', () => {
    const buttonText = 'test button text';
    const CustomButtonSpy = jest.spyOn(CustomButtonModule.default, 'render');
    const onClickStub = () => {};
    render(
      <ErrorPage
        header={'test header'}
        subtitle={'test subtitle'}
        variant={'apiLoader'}
        buttonText={buttonText}
        onClick={onClickStub}
      />
    );

    expect(CustomButtonSpy).toHaveBeenCalledWith(
      {
        className: 'error-page-button',
        text: buttonText,
        variant: 'primary',
        onClick: onClickStub
      },
      null
    );

    const button = screen.getByRole('button');
    expect(button).toHaveTextContent(buttonText);
    expect(button.onclick).toStrictEqual(expect.any(Function));
  });

  it('has no onClick callback when it is not provided', () => {
    const buttonText = 'test button text';
    const CustomButtonSpy = jest.spyOn(CustomButtonModule.default, 'render');

    render(
      <ErrorPage header={'test header'} subtitle={'test subtitle'} variant={'apiLoader'} buttonText={buttonText} />
    );

    expect(CustomButtonSpy).toHaveBeenCalledWith(
      {
        className: 'error-page-button',
        text: buttonText,
        variant: 'primary',
        onClick: undefined
      },
      null
    );

    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
    expect(button.onclick).toBe(null);
  });
});
