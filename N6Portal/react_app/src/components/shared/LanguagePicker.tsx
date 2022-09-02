import { FC } from 'react';
import classNames from 'classnames';
import { useTypedIntl } from 'utils/useTypedIntl';
import { ReactComponent as Pl } from 'images/pl-icon.svg';
import { ReactComponent as En } from 'images/en-icon.svg';
import useLanguageContext from 'context/LanguageProvider';

interface IProps {
  mode: 'text' | 'icon';
  fullDictName?: boolean;
  buttonClassName?: string;
}

const LanguagePicker: FC<IProps> = ({ mode, fullDictName, buttonClassName }) => {
  const { handleChangeLang } = useLanguageContext();
  const { locale, messages } = useTypedIntl();
  return (
    <>
      <button
        onClick={() => handleChangeLang('en')}
        className={classNames('language-picker-button p-0', buttonClassName, { selected: locale === 'en' })}
        aria-label={`${messages.language_picker_aria_label}`}
      >
        {mode === 'icon' ? <En /> : fullDictName ? messages.language_picker_en : messages.language_picker_en_short}
      </button>
      {mode === 'text' && !fullDictName && <span> | </span>}
      <button
        onClick={() => handleChangeLang('pl')}
        className={classNames('language-picker-button p-0', buttonClassName, { selected: locale === 'pl' })}
        aria-label={`${messages.language_picker_aria_label}`}
      >
        {mode === 'icon' ? <Pl /> : fullDictName ? messages.language_picker_pl : messages.language_picker_pl_short}
      </button>
    </>
  );
};

export default LanguagePicker;
