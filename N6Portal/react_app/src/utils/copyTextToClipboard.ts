import { noop } from 'utils/noop';

export const copyTextToClipboard = (text?: string | null, successCallback = noop): void => {
  if (!text) return;

  try {
    navigator.clipboard.writeText(text);
    successCallback();
  } catch {}
};
