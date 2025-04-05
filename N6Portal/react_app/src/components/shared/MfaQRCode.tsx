import { FC, useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { useTypedIntl } from 'utils/useTypedIntl';
import { IMfaConfig } from 'api/auth/types';

const MfaQRCode: FC<IMfaConfig['mfa_config']> = (props) => {
  const secret_key = props?.secret_key;
  const secret_key_qr_code_url = props?.secret_key_qr_code_url;
  const [qrcodeError, toggleQrcodeError] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { messages } = useTypedIntl();

  // render QRcode
  useEffect(() => {
    if (!secret_key_qr_code_url || !canvasRef.current) return;
    QRCode.toCanvas(canvasRef.current, secret_key_qr_code_url, (error) => {
      if (error) toggleQrcodeError(true);
    });
  }, [secret_key_qr_code_url]);

  return (
    <div className="mfa-config-qrcode-wrapper">
      <div className="mfa-config-qr-code">
        <canvas ref={canvasRef} data-testid="mfa_qr_code" />
        {qrcodeError && (
          <div className="qr-code-placeholder-wrapper">
            <div className="qr-code-placeholder" data-testid="mfa_error_info">
              {messages.login_mfa_qrcode_placeholder_text}
            </div>
          </div>
        )}
      </div>
      <div>
        <p data-testid="mfa_key_label">{messages.login_mfa_config_key_label}</p>
        <p data-testid="mfa_secret_key">{secret_key}</p>
      </div>
    </div>
  );
};

export default MfaQRCode;
