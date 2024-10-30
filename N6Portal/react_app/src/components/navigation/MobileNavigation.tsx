import { FC, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Dropdown } from 'react-bootstrap';
import classNames from 'classnames';
import { useTypedIntl } from 'utils/useTypedIntl';
import routeList from 'routes/routeList';
import { ReactComponent as Chevron } from 'images/chevron.svg';
import useAuthContext from 'context/AuthContext';

const MobileNavigation: FC = () => {
  const { knowledgeBaseEnabled } = useAuthContext();
  const { messages } = useTypedIntl();
  const { pathname } = useLocation();
  const [isOpen, setIsOpen] = useState(false);

  const dropdownHeaders = {
    [routeList.organization]: messages.header_nav_organization,
    [routeList.incidents]: messages.header_nav_incidents,
    [routeList.account]: messages.header_nav_organization,
    [routeList.knowledgeBase]: messages.header_nav_knowledge_base
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
        {knowledgeBaseEnabled && (
          <>
            <Dropdown.Divider className="m-0" />
            <Dropdown.Item as={Link} to={routeList.knowledgeBase} className="p-3">
              {messages.header_nav_knowledge_base}
            </Dropdown.Item>
          </>
        )}
      </Dropdown.Menu>
    </Dropdown>
  );
};

export default MobileNavigation;
