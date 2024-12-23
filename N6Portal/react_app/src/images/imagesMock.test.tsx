/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render } from '@testing-library/react';
import { ReactComponent as ErrorIco } from 'images/error_ico.svg';
import { ReactComponent as ExpandIco } from 'images/expand-ico.svg';
import { ReactComponent as LogoN6 } from 'images/logo_n6.svg';
import { ReactComponent as Hierarchy } from 'images/hierarchy.svg';
import { ReactComponent as Download } from 'images/download.svg';
import { ReactComponent as Ok } from 'images/ok.svg';
import { ReactComponent as Restore } from 'images/restore.svg';
import { ReactComponent as Update } from 'images/update.svg';
import { ReactComponent as Chevron } from 'images/chevron.svg';
import { ReactComponent as PlIcon } from 'images/pl-icon.svg';
import { ReactComponent as QuestionMark } from 'images/question_mark.svg';
import { ReactComponent as Search } from 'images/search.svg';
import { ReactComponent as User } from 'images/user.svg';
import { ReactComponent as ArrowIco } from 'images/arrow_ico.svg';
import { ReactComponent as Avatar } from 'images/avatar.svg';
import { ReactComponent as EnIcon } from 'images/en-icon.svg';
import { ReactComponent as SuccessIco } from 'images/success_ico.svg';
import { ReactComponent as CheckIco } from 'images/check-ico.svg';
import { ReactComponent as UserSettingsMfa } from 'images/user-settings-mfa.svg';
import { ReactComponent as Error } from 'images/error.svg';
import { ReactComponent as Plus } from 'images/plus.svg';
import { ReactComponent as Email } from 'images/email.svg';
import { ReactComponent as RightArrow } from 'images/right_arrow.svg';
import { ReactComponent as Calendar } from 'images/calendar.svg';
import { ReactComponent as NotFoundIcon } from 'images/not-found-icon.svg';
import { ReactComponent as UserSettingsApiKey } from 'images/user-settings-api-key.svg';
import { ReactComponent as NoResources } from 'images/no-resources.svg';
import { ReactComponent as Close } from 'images/close.svg';
import { ReactComponent as CompressIco } from 'images/compress-ico.svg';
import { ReactComponent as KbBook } from 'images/kb-book.svg';
import { ReactComponent as NoAccessIcon } from 'images/no-access-icon.svg';
import { ReactComponent as Reset } from 'images/reset.svg';
import { ReactComponent as Appointment } from 'images/appointment.svg';
import { ReactComponent as ApiError } from 'images/api-error.svg';

describe('icons', () => {
  it('error_ico.svg', () => {
    const { container } = render(<ErrorIco />);
    expect(container.querySelector('svg-error-ico-mock')).toBeInTheDocument();
  });

  it('expand-ico.svg', () => {
    const { container } = render(<ExpandIco />);
    expect(container.querySelector('svg-expand-ico-mock')).toBeInTheDocument();
  });

  it('logo_n6.svg', () => {
    const { container } = render(<LogoN6 />);
    expect(container.querySelector('svg-logo-n6-mock')).toBeInTheDocument();
  });

  it('hierarchy.svg', () => {
    const { container } = render(<Hierarchy />);
    expect(container.querySelector('svg-hierarchy-mock')).toBeInTheDocument();
  });

  it('download.svg', () => {
    const { container } = render(<Download />);
    expect(container.querySelector('svg-download-mock')).toBeInTheDocument();
  });

  it('ok.svg', () => {
    const { container } = render(<Ok />);
    expect(container.querySelector('svg-ok-mock')).toBeInTheDocument();
  });

  it('restore.svg', () => {
    const { container } = render(<Restore />);
    expect(container.querySelector('svg-restore-mock')).toBeInTheDocument();
  });

  it('update.svg', () => {
    const { container } = render(<Update />);
    expect(container.querySelector('svg-update-mock')).toBeInTheDocument();
  });

  it('chevron.svg', () => {
    const { container } = render(<Chevron />);
    expect(container.querySelector('svg-chevron-mock')).toBeInTheDocument();
  });

  it('pl-icon.svg', () => {
    const { container } = render(<PlIcon />);
    expect(container.querySelector('svg-pl-icon-mock')).toBeInTheDocument();
  });

  it('question_mark.svg', () => {
    const { container } = render(<QuestionMark />);
    expect(container.querySelector('svg-question-mark-mock')).toBeInTheDocument();
  });

  it('search.svg', () => {
    const { container } = render(<Search />);
    expect(container.querySelector('svg-search-mock')).toBeInTheDocument();
  });

  it('user.svg', () => {
    const { container } = render(<User />);
    expect(container.querySelector('svg-user-mock')).toBeInTheDocument();
  });

  it('arrow_ico.svg', () => {
    const { container } = render(<ArrowIco />);
    expect(container.querySelector('svg-arrow-ico-mock')).toBeInTheDocument();
  });

  it('avatar.svg', () => {
    const { container } = render(<Avatar />);
    expect(container.querySelector('svg-avatar-mock')).toBeInTheDocument();
  });

  it('en-icon.svg', () => {
    const { container } = render(<EnIcon />);
    expect(container.querySelector('svg-en-icon-mock')).toBeInTheDocument();
  });

  it('success_ico.svg', () => {
    const { container } = render(<SuccessIco />);
    expect(container.querySelector('svg-success-ico-mock')).toBeInTheDocument();
  });

  it('check-ico.svg', () => {
    const { container } = render(<CheckIco />);
    expect(container.querySelector('svg-check-ico-mock')).toBeInTheDocument();
  });

  it('user-settings-mfa.svg', () => {
    const { container } = render(<UserSettingsMfa />);
    expect(container.querySelector('svg-user-settings-mfa-mock')).toBeInTheDocument();
  });

  it('error.svg', () => {
    const { container } = render(<Error />);
    expect(container.querySelector('svg-error-mock')).toBeInTheDocument();
  });

  it('plus.svg', () => {
    const { container } = render(<Plus />);
    expect(container.querySelector('svg-plus-mock')).toBeInTheDocument();
  });

  it('email.svg', () => {
    const { container } = render(<Email />);
    expect(container.querySelector('svg-email-mock')).toBeInTheDocument();
  });

  it('right_arrow.svg', () => {
    const { container } = render(<RightArrow />);
    expect(container.querySelector('svg-right-arrow-mock')).toBeInTheDocument();
  });

  it('calendar.svg', () => {
    const { container } = render(<Calendar />);
    expect(container.querySelector('svg-calendar-mock')).toBeInTheDocument();
  });

  it('not-found-icon.svg', () => {
    const { container } = render(<NotFoundIcon />);
    expect(container.querySelector('svg-not-found-icon-mock')).toBeInTheDocument();
  });

  it('user-settings-api-key.svg', () => {
    const { container } = render(<UserSettingsApiKey />);
    expect(container.querySelector('svg-user-settings-api-key-mock')).toBeInTheDocument();
  });

  it('no-resources.svg', () => {
    const { container } = render(<NoResources />);
    expect(container.querySelector('svg-no-resources-mock')).toBeInTheDocument();
  });

  it('close.svg', () => {
    const { container } = render(<Close />);
    expect(container.querySelector('svg-close-mock')).toBeInTheDocument();
  });

  it('compress-ico.svg', () => {
    const { container } = render(<CompressIco />);
    expect(container.querySelector('svg-compress-ico-mock')).toBeInTheDocument();
  });

  it('kb-book.svg', () => {
    const { container } = render(<KbBook />);
    expect(container.querySelector('svg-kb-book-mock')).toBeInTheDocument();
  });

  it('no-access-icon.svg', () => {
    const { container } = render(<NoAccessIcon />);
    expect(container.querySelector('svg-no-access-icon-mock')).toBeInTheDocument();
  });

  it('reset.svg', () => {
    const { container } = render(<Reset />);
    expect(container.querySelector('svg-reset-mock')).toBeInTheDocument();
  });

  it('appointment.svg', () => {
    const { container } = render(<Appointment />);
    expect(container.querySelector('svg-appointment-mock')).toBeInTheDocument();
  });

  it('api-error.svg', () => {
    const { container } = render(<ApiError />);
    expect(container.querySelector('svg-api-error-mock')).toBeInTheDocument();
  });
});
