import { FC, Ref, MouseEvent, ButtonHTMLAttributes, ReactElement, forwardRef } from 'react';
import { Link } from 'react-router-dom';
import classNames from 'classnames';
import { Button } from 'react-bootstrap';
import LoadingSpinner from 'components/shared/LoadingSpinner';

interface IProps extends ButtonHTMLAttributes<Element> {
  variant: 'primary' | 'secondary' | 'outline' | 'filter' | 'link';
  icon?: ReactElement;
  iconPlacement?: 'right' | 'left';
  ariaLabel?: string;
  className?: string;
  text: string;
  disabled?: boolean;
  loading?: boolean;
  to?: string;
  href?: string;
}

const CustomButton: FC<IProps> = forwardRef(
  (
    {
      variant,
      icon,
      iconPlacement,
      ariaLabel,
      className,
      text,
      disabled,
      loading,
      onClick,
      type = 'button',
      to = '',
      href
    },
    ref: Ref<HTMLAnchorElement>
  ) => {
    const spinnerColor = ['outline', 'link'].includes(variant) ? 'currentColor' : '#ffffff';
    return (
      <Button
        className={classNames('n6-button', variant, className, {
          disabled,
          loading
        })}
        onClick={onClick ? (e: MouseEvent) => onClick(e) : undefined}
        disabled={disabled}
        type={to || href ? undefined : type}
        as={to ? Link : undefined}
        to={to}
        href={href}
        target={href ? '_blank' : undefined}
        rel={href ? 'noopener noreferrer' : undefined}
        aria-label={ariaLabel}
        variant=""
        ref={ref}
      >
        {!loading && icon && iconPlacement && <span className={`n6-button-icon ${iconPlacement}`}>{icon}</span>}
        {!loading && <span>{text}</span>}
        {loading && <LoadingSpinner color={spinnerColor} />}
      </Button>
    );
  }
);

export default CustomButton;
