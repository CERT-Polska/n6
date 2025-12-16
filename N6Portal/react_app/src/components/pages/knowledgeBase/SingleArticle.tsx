import { FC, useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxtHighlighter } from 'react-syntax-highlighter';
import FileSaver from 'file-saver';
import remarkGfm from 'remark-gfm';
import rehypeAutolinkHeadings from 'rehype-autolink-headings';
import rehypeCustomAnchorPlugin from 'utils/rehypeCustomAnchorPlugin';
import { useTypedIntl } from 'utils/useTypedIntl';
import { useArticle } from 'api/services/kb';
import Loader from 'components/loading/Loader';
import SingleArticlePlaceholder from 'components/pages/knowledgeBase/SingleArticlePlaceholder';
import useChapterCollapseContext from 'context/ChapterCollapseContext';
import CustomButton from 'components/shared/CustomButton';
import { ReactComponent as DownloadIcon } from 'images/download.svg';
import { getArticlePdfFile } from 'api/services/kb/getArticlePdfFile';

const SingleArticle: FC = () => {
  const [downloadPdfError, setDownloadPdfError] = useState(false);
  const { setActiveArticleId } = useChapterCollapseContext();
  const { messages, locale } = useTypedIntl();

  const scrollToRef = useRef<HTMLDivElement>(null);

  const { articleId } = useParams<{ articleId: string }>();
  const articleIdRegexp = /^[1-9]\d{0,5}$/;
  const parsedArticleId = articleIdRegexp.test(articleId) ? articleId : undefined;

  const { data, isError, error, isLoading } = useArticle(articleId, { enabled: !!parsedArticleId });

  useEffect(() => {
    setDownloadPdfError(false);
    setActiveArticleId(parsedArticleId);

    if (!window.location.hash) {
      scrollToRef.current?.scrollIntoView({ block: 'center' });
    }
  }, [parsedArticleId, setActiveArticleId]);

  useEffect(() => {
    if (data && window.location.hash) {
      const id = window.location.hash.substring(1);
      const element = document.getElementById(id);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [data]);

  if (isLoading) {
    return (
      <article className="kb-article d-flex align-items-center">
        <Loader />
      </article>
    );
  }

  const notFoundArticle = isError && error?.response?.status === 404;
  if (!parsedArticleId || notFoundArticle || !data) {
    const subtitle = !parsedArticleId
      ? messages['knowledge_base_invalid_article_id']
      : notFoundArticle
        ? messages['knowledge_base_article_not_found']
        : messages['knowledge_base_request_error'];

    return <SingleArticlePlaceholder subtitle={`${subtitle}`} />;
  }

  const downloadPdfFile = async () => {
    setDownloadPdfError(false);
    if (!parsedArticleId) return;
    try {
      const payload = await getArticlePdfFile(parsedArticleId, locale);
      FileSaver.saveAs(payload, `article-${parsedArticleId}-${locale}.pdf`);
    } catch {
      setDownloadPdfError(true);
    }
  };

  return (
    <>
      <div ref={scrollToRef} />
      <article className="kb-article" data-testid="kb-article">
        <div className="article-pdf-download">
          <CustomButton
            text={`${messages['knowledge_base_download_pdf']}`}
            icon={<DownloadIcon data-testid="kb-article-download-pdf-icon" />}
            onClick={downloadPdfFile}
            iconPlacement="left"
            variant="link"
            dataTestId="kb-article-download-pdf-button"
          />
          {downloadPdfError && (
            <p data-testid="kb-article-download-pdf-error" className="font-smaller text-danger pdf-download-error">
              {messages['knowledge_base_download_failed']}
            </p>
          )}
        </div>
        <div data-testid="kb-article-markdown">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeCustomAnchorPlugin, [rehypeAutolinkHeadings, { behavior: 'wrap' }]]}
            className="md-content"
            children={data.content[locale]}
            components={{
              code({ node: _node, inline, className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <SyntaxtHighlighter children={String(children).replace(/\n$/, '')} language={match[1]} {...props} />
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              }
            }}
          />
        </div>
      </article>
    </>
  );
};

export default SingleArticle;
