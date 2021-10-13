import { FC } from 'react';
import { useLocation } from 'react-router-dom';
import routeList from 'routes/routeList';
import LanguagePicker from 'components/shared/LanguagePicker';

const Footer: FC = () => {
  const { pathname } = useLocation();
  const pathsWithFooter = [routeList.login, routeList.forgotPassword];

  if (!pathsWithFooter.includes(pathname)) return null;

  return (
    <footer className="page-footer d-flex justify-content-center align-items-center">
      <LanguagePicker mode="text" fullDictName buttonClassName="m-2" />
    </footer>
  );
};

export default Footer;
