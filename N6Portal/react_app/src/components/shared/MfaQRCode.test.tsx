import { render, screen } from '@testing-library/react';
import MfaQRCode from './MfaQRCode';
import { LanguageProviderTestWrapper } from 'utils/testWrappers';
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
      <LanguageProviderTestWrapper>
        <MfaQRCode secret_key={secret_key} secret_key_qr_code_url={secret_key_qr_code_url} />
      </LanguageProviderTestWrapper>
    );

    const wrapper = container.firstChild;
    expect(wrapper?.childNodes).toHaveLength(2);

    const canvas = wrapper?.firstChild?.firstChild;
    expect(canvas).toStrictEqual(expect.any(HTMLCanvasElement));
    expect(QRCodeToCanvasSpy).toHaveBeenCalledWith(
      expect.objectContaining(canvasMock),
      secret_key_qr_code_url,
      expect.any(Function)
    );

    const secretKeyWrapper = wrapper?.childNodes[1];
    expect(secretKeyWrapper?.childNodes).toHaveLength(2);
    expect(secretKeyWrapper?.firstChild).toHaveTextContent('Secret key:');
    expect(secretKeyWrapper?.childNodes[1]).toHaveTextContent(secret_key);
  });

  it('renders error message when writing to canvas component throws error', () => {
    const secret_key = 'test secret key';
    const secret_key_qr_code_url = 'test secret key qr code url';

    // QRCode.toCanvas() by default fails in this test because of lack of canvas context in test env
    render(
      <LanguageProviderTestWrapper>
        <MfaQRCode secret_key={secret_key} secret_key_qr_code_url={secret_key_qr_code_url} />
      </LanguageProviderTestWrapper>
    );

    expect(screen.getByText(dictionary['en']['login_mfa_qrcode_placeholder_text'])).toBeInTheDocument();
  });
});
