import { FC, useEffect, useRef, useState } from 'react';
import { useIntl } from 'react-intl';
import QRCode from 'qrcode';
import { IMfaConfig } from 'api/auth/types';

const MfaQRCode: FC<IMfaConfig['mfa_config']> = ({ secret_key, secret_key_qr_code_url }) => {
  const [qrcodeError, toggleQrcodeError] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { messages } = useIntl();

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
        <canvas ref={canvasRef} />
        {qrcodeError && (
          <div className="qr-code-placeholder-wrapper">
            <div className="qr-code-placeholder">{messages.login_mfa_qrcode_placeholder_text}</div>
          </div>
        )}
      </div>
      <div>
        <p>{messages.login_mfa_config_key_label}</p>
        <p>{secret_key}</p>
      </div>
    </div>
  );
};

export default MfaQRCode;
