/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { cleanup, render } from '@testing-library/react';
import FormDevTools from './FormDevTools';
import { Control } from 'react-hook-form';
import * as DevToolModule from '@hookform/devtools';

describe('<FormDevTools />', () => {
  const OLD_NODE_ENV = process.env.NODE_ENV;

  afterEach(() => {
    cleanup();
    process.env = Object.assign(process.env, {
      NODE_ENV: OLD_NODE_ENV
    });
  });

  it('calls for "react-hook-form" DevTools in form-devtools wrapper \
        if current environment is development', () => {
    const controlProps = {} as Control;
    const hookformDevToolsSpy = jest.spyOn(DevToolModule, 'DevTool').mockReturnValue(<h6 className="DevToolMock" />);
    process.env = Object.assign(process.env, {
      NODE_ENV: 'development'
    });

    const { container } = render(<FormDevTools control={controlProps} />);
    expect(container).not.toBeEmptyDOMElement();
    expect(container.firstChild).toHaveClass('form-devtools');
    expect(container.firstChild?.firstChild).toHaveClass('DevToolMock');
    expect(hookformDevToolsSpy).toHaveBeenCalledWith({ control: controlProps }, {});
  });

  it('returns nothing if current environment is not development', () => {
    const { container } = render(<FormDevTools control={{} as Control} />);
    expect(container).toBeEmptyDOMElement();
  });
});
