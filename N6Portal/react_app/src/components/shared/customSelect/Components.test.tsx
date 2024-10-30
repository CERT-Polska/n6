/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import { Control, DropdownIndicator } from './Components';
import { SelectOption } from './CustomSelect';
import { ControlProps, IndicatorProps } from 'react-select';
import { IMatchMediaContext, MatchMediaContext } from 'context/MatchMediaContext';

describe('<Control />', () => {
  it.each([{ isXs: true }, { isXs: false }])(
    'renders components.Control element from "react-select" with additional icon if provided and component size is small enough',
    ({ isXs }) => {
      const children = <div className="test-children-component" />;
      const props = {
        icon: <img className="test-img-component" />,
        getStyles: jest.fn(),
        cx: jest.fn(),
        children: children
      } as unknown as ControlProps<SelectOption<string>, boolean>;
      const { container } = render(
        <MatchMediaContext.Provider value={{ isXs: isXs } as IMatchMediaContext}>
          <Control {...props} />
        </MatchMediaContext.Provider>
      );

      expect(container.firstChild).toHaveClass('css-0');
      if (!isXs) {
        const img = screen.getByRole('img', { name: 'Ikona w rozwijanej liście' });
        expect(img).toHaveClass('custom-select-icon');
        expect(img.firstChild).toHaveClass('test-img-component');
        expect(img.parentElement?.childNodes[1]).toHaveClass('test-children-component');
      } else {
        expect(container.firstChild?.firstChild).toHaveClass('test-children-component');
      }
    }
  );
});

describe('<DropdownIndicator />', () => {
  it('renders components.Control element from "react-select" with additional icon', () => {
    const props = { getStyles: jest.fn(), cx: jest.fn() } as unknown as IndicatorProps<SelectOption<string>, boolean>;
    const { container } = render(<DropdownIndicator {...props} />);

    expect(container.firstChild).toHaveClass('css-0');
    expect(container.querySelector('svg-arrow-ico-mock')?.parentElement).toBe(container.firstChild); //TODO: customize
  });
});
