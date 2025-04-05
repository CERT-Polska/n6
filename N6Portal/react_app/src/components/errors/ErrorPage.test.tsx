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

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(textHeader);
      expect(screen.getByText(textSubtitle)).toHaveRole('paragraph');

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

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(textHeader);
    expect(screen.getByText(textSubtitle)).toHaveRole('paragraph');

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
        dataTestId="testID"
      />
    );

    expect(CustomButtonSpy).toHaveBeenCalledWith(
      {
        className: 'error-page-button',
        text: buttonText,
        variant: 'primary',
        onClick: onClickStub,
        dataTestId: 'testID_btn'
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
      <ErrorPage
        header={'test header'}
        subtitle={'test subtitle'}
        variant={'apiLoader'}
        buttonText={buttonText}
        dataTestId="testID"
      />
    );

    expect(CustomButtonSpy).toHaveBeenCalledWith(
      {
        className: 'error-page-button',
        text: buttonText,
        variant: 'primary',
        onClick: undefined,
        dataTestId: 'testID_btn'
      },
      null
    );

    const button = screen.getByRole('button');
    expect(button).toBeInTheDocument();
    expect(button.onclick).toBe(null);
  });
});
