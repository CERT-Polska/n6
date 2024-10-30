/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, render, screen } from '@testing-library/react';
import FormFeedback from './FormFeedback';
import { TApiResponse } from './utils';

describe('<FormFeedback />', () => {
  afterEach(() => cleanup());

  it.each([{ response: 'success' }, { response: 'error' }])(
    'renders forwardRef with given ref; classname and icon corresponding \
        to the response and given message',
    ({ response }) => {
      const message = 'test message';
      const { container } = render(
        <FormFeedback response={response as Exclude<TApiResponse, undefined>} message={message} />
      );
      expect(container.firstChild).toHaveClass(`form-feedback mt-4 ${response}`);
      expect(
        container.querySelector(response === 'success' ? 'svg-check-ico-mock' : 'svg-error-mock')
      ).toBeInTheDocument();
      expect(screen.getByText(message)).toHaveRole('paragraph');
    }
  );
});
