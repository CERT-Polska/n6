/**
 * @jest-environment jsdom
 */

import '@testing-library/jest-dom';
import { render, screen } from '@testing-library/react';
import MfaQRCode from './MfaQRCode';
import { LanguageProvider } from 'context/LanguageProvider';
import QRCode from 'qrcode';
import { dictionary } from 'dictionary';

describe('<MfaORCode/>', () => {
  it('renders QR code for given MFA config or error message', () => {
    const secret_key = 'test secret key';
    const secret_key_qr_code_url = 'test secret key qr code url';

    const canvasMock = <img className="mock" />;

    const QRCodeToCanvasSpy = jest
      .spyOn(QRCode, 'toCanvas')
      .mockImplementation((refCurrent, _key, _errorCallback) => Object.assign(refCurrent, canvasMock));

    const { container } = render(
      <LanguageProvider>
        <MfaQRCode secret_key={secret_key} secret_key_qr_code_url={secret_key_qr_code_url} />
      </LanguageProvider>
    );

    const wrapper = container.firstChild;
    expect(wrapper).toHaveClass('mfa-config-qrcode-wrapper');
    expect(wrapper?.childNodes).toHaveLength(2);

    const canvasWrapper = wrapper?.firstChild;
    expect(canvasWrapper).toHaveClass('mfa-config-qr-code');

    const canvas = canvasWrapper?.firstChild;
    expect(canvas).toStrictEqual(expect.any(HTMLCanvasElement));
    expect(QRCodeToCanvasSpy).toHaveBeenCalledWith(
      expect.objectContaining(canvasMock),
      secret_key_qr_code_url,
      expect.any(Function)
    );

    const secretKeyWrapper = wrapper?.childNodes[1];
    expect(secretKeyWrapper?.childNodes).toHaveLength(2);
    expect(secretKeyWrapper?.firstChild).toHaveTextContent(dictionary['en']['login_mfa_config_key_label']);
    expect(secretKeyWrapper?.childNodes[1]).toHaveTextContent(secret_key);
  });

  it('renders error message when writing to canvas component throws error', () => {
    const secret_key = 'test secret key';
    const secret_key_qr_code_url = 'test secret key qr code url';

    // QRCode.toCanvas() by default fails in this test because of lack of canvas context in test env
    render(
      <LanguageProvider>
        <MfaQRCode secret_key={secret_key} secret_key_qr_code_url={secret_key_qr_code_url} />
      </LanguageProvider>
    );

    const QRCodePlaceholder = screen.getByText(dictionary['en']['login_mfa_qrcode_placeholder_text']);
    expect(QRCodePlaceholder).toHaveClass('qr-code-placeholder');
    expect(QRCodePlaceholder.parentElement).toHaveClass('qr-code-placeholder-wrapper');
    expect(QRCodePlaceholder.parentElement?.parentElement).toHaveClass('mfa-config-qr-code');
  });
});
