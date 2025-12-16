import { FC } from 'react';
import { sanitizeUrl } from '@braintree/sanitize-url';
import { INameDetails } from 'api/services/globalTypes';
import { useTypedIntl } from 'utils/useTypedIntl';

type EnrichmentModalContentProps = {
  nameDetailsData: INameDetails | null;
};

const collectUrlsInPreferredOrder = (sources: any): string[] => {
  if (!sources) return [];

  const preferredOrder = ['moje', 'enisa', 'knowledge_base'];
  const allUrls: string[] = [];

  preferredOrder.forEach((key) => {
    const value = sources[key];
    if (Array.isArray(value) && value.length > 0) {
      allUrls.push(...value);
    }
  });

  Object.keys(sources)
    .filter((k) => !preferredOrder.includes(k))
    .sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
    .forEach((k) => {
      const value = sources[k];
      if (Array.isArray(value) && value.length > 0) {
        allUrls.push(...value);
      }
    });

  return allUrls;
};

const usePickKnowledgeProvider = (url: string): string | JSX.Element => {
  const { messages } = useTypedIntl();

  if (url.includes('euvd.enisa.europa.eu')) {
    return (
      <>
        {messages.incidents_extended_name_provider_enisa}
        <b>{messages.enisa_database}</b>
      </>
    );
  }

  if (url.includes('moje.cert.pl')) {
    return (
      <>
        {messages.incidents_extended_name_provider_moje_text}
        <b>{messages.moje_cert_pl}</b>
      </>
    );
  }

  if (url.includes('/knowledge_base/articles')) {
    return (
      <>
        {messages.incidents_extended_name_provider_kb}
        <b>{messages.incident_kb_n6}</b>
      </>
    );
  }

  return url;
};

const renderSection = (title: string, sources: any, messages: Record<string, string>) => {
  const allUrls = collectUrlsInPreferredOrder(sources);

  if (allUrls.length === 0) return null;

  return (
    <div key={title} className="mb-3">
      <h6 className="mb-2">
        {messages.incidents_extended_name_about}
        <i>{title}</i>
      </h6>
      <ul className="mb-0">
        {allUrls.map((url) => {
          const sanitizedUrl = sanitizeUrl(url);
          if (sanitizedUrl === 'about:blank') return null;

          return (
            <li key={sanitizedUrl}>
              <a href={sanitizedUrl} target="_blank" rel="noopener noreferrer">
                {usePickKnowledgeProvider(sanitizedUrl)}
              </a>
            </li>
          );
        })}
      </ul>
    </div>
  );
};

export const EnrichmentModalContent: FC<EnrichmentModalContentProps> = ({ nameDetailsData }) => {
  const { messages } = useTypedIntl();
  if (!nameDetailsData) {
    return <p className="text-muted">{messages.incidents_extended_name_no_data_info}</p>;
  }

  const cveData = nameDetailsData.cve || {};
  const phraseData = nameDetailsData.phrase || {};

  const hasCveData = Object.keys(cveData).length > 0;
  const hasPhraseData = Object.keys(phraseData).length > 0;

  if (!hasCveData && !hasPhraseData) {
    return <p className="text-muted">{messages.incidents_extended_name_no_data_info}</p>;
  }

  return (
    <>
      {Object.entries(cveData)
        .sort(([aKey], [bKey]) => aKey.localeCompare(bKey, undefined, { sensitivity: 'base' }))
        .map(([cveId, sources]) => renderSection(cveId.toUpperCase(), sources, messages))}
      {Object.entries(phraseData)
        .sort(([aKey], [bKey]) => aKey.localeCompare(bKey, undefined, { sensitivity: 'base' }))
        .map(([categoryName, sources]) => renderSection(categoryName, sources, messages))}
    </>
  );
};
