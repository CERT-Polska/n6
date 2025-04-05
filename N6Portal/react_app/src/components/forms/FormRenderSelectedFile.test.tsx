import { cleanup, render } from '@testing-library/react';
import FormRenderSelectedFile from './FormRenderSelectedFile';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
const CustomButtonModule = require('components/shared/CustomButton');

describe('<FormRenderSelectedFile />', () => {
  afterEach(() => cleanup());

  it.each([
    { filename: 'test.txt', expectedFilePrefix: 'test', expectedFileSuffix: 'txt' },
    { filename: '', expectedFilePrefix: '', expectedFileSuffix: '.' }, // seems unexpected
    {
      filename: 'filename with spaces and ęśąćź$%!@#:::,.blahblahblah',
      expectedFilePrefix: 'filename with spaces and ęśąćź$%!@#:::,',
      expectedFileSuffix: 'blahblahblah'
    },
    { filename: 'filenameWithoutADot', expectedFilePrefix: '', expectedFileSuffix: '.filenameWithoutADot' }, // seems unexpected
    { filename: 'multiple..dots', expectedFilePrefix: 'multiple', expectedFileSuffix: '.dots' },
    { filename: '.surroundedbydots.', expectedFilePrefix: 'surroundedbydots', expectedFileSuffix: '.' },
    { filename: 't.e.s.t', expectedFilePrefix: 'tes', expectedFileSuffix: '.t' }
  ])(
    'renders CustomButton in classnamed container with filename adn extension of given filename',
    ({ filename, expectedFilePrefix, expectedFileSuffix }) => {
      const onClickMock = jest.fn();
      const CustomButtonSpy = jest
        .spyOn(CustomButtonModule.default, 'render')
        .mockReturnValue(<h4 className="mock-custom-button" />);

      const { container } = render(
        <LanguageProviderTestWrapper>
          <FormRenderSelectedFile filename={filename} onClick={onClickMock} />
        </LanguageProviderTestWrapper>
      );

      const paragraphs = (container.firstChild as HTMLElement).querySelectorAll('div');
      expect(paragraphs.length).toBe(2);
      expect(paragraphs[0]).toHaveClass('form-render-file-name');
      expect(paragraphs[0]).toHaveTextContent(expectedFilePrefix);
      expect(paragraphs[1]).toHaveClass('form-render-file-extension');
      expect(paragraphs[1]).toHaveTextContent(expectedFileSuffix);

      expect(CustomButtonSpy).toHaveBeenCalledWith(
        {
          variant: 'secondary',
          text: `Replace file`,
          className: 'form-render-btn-replace ml-3',
          onClick: onClickMock
        },
        null
      );
    }
  );
});
