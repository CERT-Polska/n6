import { FC, useState } from 'react';
import { useIntl } from 'react-intl';
import { Link, useLocation } from 'react-router-dom';
import Dropdown from 'react-bootstrap/esm/Dropdown';
import classNames from 'classnames';
import routeList from 'routes/routeList';
import { ReactComponent as Chevron } from 'images/chevron.svg';

const MobileNavigation: FC = () => {
  const { messages } = useIntl();
  const { pathname } = useLocation();
  const [isOpen, setIsOpen] = useState(false);

  const dropdownHeaders = {
    [routeList.organization]: messages.header_nav_organization,
    [routeList.incidents]: messages.header_nav_incidents,
    [routeList.account]: messages.header_nav_organization
  };

  return (
    <Dropdown onToggle={(isOpen) => setIsOpen(isOpen)} className="mr-4 ml-auto">
      <Dropdown.Toggle
        id="dropdown-user-menu"
        aria-label={`${messages.header_user_menu_aria_label}`}
        bsPrefix="header-user-btn"
        className="light-focus"
      >
        <span className="font-bigger font-weight-medium header-mobile-dropdown-title mr-2">
          {dropdownHeaders[pathname]}
        </span>
        <Chevron className={classNames('header-dropdown-chevron', { open: isOpen })} />
      </Dropdown.Toggle>
      <Dropdown.Menu align="right" className="header-dropdown-menu p-0">
        <Dropdown.Item as={Link} to={routeList.organization} className="p-3">
          {messages.header_nav_organization}
        </Dropdown.Item>
        <Dropdown.Divider className="m-0" />
        <Dropdown.Item as={Link} to={routeList.incidents} className="p-3">
          {messages.header_nav_incidents}
        </Dropdown.Item>
      </Dropdown.Menu>
    </Dropdown>
  );
};

export default MobileNavigation;
