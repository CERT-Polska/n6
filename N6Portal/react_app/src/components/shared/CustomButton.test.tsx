import { cleanup, render, screen } from '@testing-library/react';
import CustomButton from './CustomButton';
import { Button } from 'react-bootstrap';
import * as LoadingSpinnerModule from './LoadingSpinner';
import { Link } from 'react-router-dom';

jest.mock('react-bootstrap', () => ({
  ...jest.requireActual('react-bootstrap'),
  Button: jest.fn()
}));
const BootstrapButtonMock = Button as jest.Mock;

describe('<CustomButton />', () => {
  afterEach(() => {
    cleanup();
    jest.resetAllMocks();
  });

  it('renders react-bootstrap Button component with given props including variant, text, icon and loading state', () => {
    BootstrapButtonMock.mockReturnValue(<h5 className="bootstrap-button" />);
    const LoadingSpinnerSpy = jest.spyOn(LoadingSpinnerModule, 'default');

    render(<CustomButton variant={'link'} text={''} />);

    expect(BootstrapButtonMock).toHaveBeenCalledWith(
      {
        'aria-label': undefined,
        as: undefined,
        // "children": [
        //   undefined,       no icon provided
        //   <span></span>,   no text provided yet gives empty span
        //   undefined,       isn't in loading state
        // ],
        children: expect.any(Array),
        className: 'n6-button link',
        disabled: undefined,
        href: undefined,
        onClick: undefined,
        rel: undefined,
        target: undefined,
        to: '',
        type: 'button',
        variant: '' // regardless of given variant
      },
      {}
    );
    expect(LoadingSpinnerSpy).not.toHaveBeenCalled();
  });

  it.each([
    { loading: false, disabled: true, variant: 'link', openInNewTab: true },
    { loading: true, disabled: true, variant: 'primary', openInNewTab: false },
    { loading: false, disabled: false, variant: 'outline', openInNewTab: false },
    { loading: true, disabled: false, variant: 'filter', openInNewTab: true }
  ])('accepts multiple HTMLButtonElement and custom props', async ({ loading, disabled, variant, openInNewTab }) => {
    BootstrapButtonMock.mockImplementation(({ children }) => <div className="bootstrap-button">{children}</div>);
    const LoadingSpinnerSpy = jest
      .spyOn(LoadingSpinnerModule, 'default')
      .mockReturnValue(<h5 className="loading-spinner" />);

    const text = 'test text';
    const icon = <img />;
    const iconPlacement = 'left';
    const ariaLabel = 'test aria label';
    const className = 'test classname';
    const to = 'test to';
    const href = 'test href';

    render(
      <CustomButton
        variant={variant as 'link' | 'primary' | 'outline' | 'filter'}
        text={text}
        loading={loading}
        icon={icon}
        iconPlacement={iconPlacement}
        ariaLabel={ariaLabel}
        className={className}
        disabled={disabled}
        to={to}
        href={href}
        openInNewTab={openInNewTab}
      />
    );

    expect(BootstrapButtonMock).toHaveBeenCalledWith(
      {
        'aria-label': ariaLabel,
        as: Link,
        // "children": [
        //   !loading && <span className={`n6-button-icon ${iconPlacement}`}>{icon}</span>,
        //   !loading && <span>{text}</span>,
        //   loading && expect.any(Object)
        // ],
        children: expect.any(Array),
        className: `n6-button ${variant} ${className}${disabled ? ' disabled' : ''}${loading ? ' loading' : ''}`,
        disabled: disabled,
        href: href,
        onClick: undefined,
        rel: 'noopener noreferrer',
        target: openInNewTab ? '_blank' : undefined,
        to: to,
        type: undefined, // because of href attribute
        variant: '' // regardless of given variant
      },
      {}
    );

    if (loading === true) {
      const spinnerColor = ['outline', 'link'].includes(variant) ? 'currentColor' : '#ffffff';
      expect(LoadingSpinnerSpy).toHaveBeenCalledWith({ color: spinnerColor }, {});
    } else {
      expect(screen.getByText(text)).toBeInTheDocument();
      expect(screen.getByRole('img')).toBeInTheDocument();
    }
  });
});
