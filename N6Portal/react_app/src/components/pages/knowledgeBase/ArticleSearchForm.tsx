import { FC } from 'react';
import { FormProvider, SubmitHandler, useForm } from 'react-hook-form';
import { useHistory, useLocation } from 'react-router-dom';
import { useTypedIntl } from 'utils/useTypedIntl';
import FormActionInput from 'components/forms/FormActionInput';
import { ReactComponent as Search } from 'images/search.svg';
import { validateSearchQuery } from 'components/forms/validation/validationSchema';
import routeList from 'routes/routeList';
import { searchRegex } from 'components/forms/validation/validationRegexp';
import useChapterCollapseContext from 'context/ChapterCollapseContext';
import useKBSearchContext from 'context/KBSearchContext';

interface ISearchForm {
  query: string;
}

const ArticleSearchForm: FC = () => {
  const { setActiveArticleId } = useChapterCollapseContext();
  const { enableSearchQuery } = useKBSearchContext();
  const { messages, locale } = useTypedIntl();
  const history = useHistory();
  const location = useLocation();

  const searchQuery = location.search.split('q=')[1] ?? '';
  const isQueryValid = searchRegex.test(searchQuery);

  const methods = useForm<ISearchForm>({
    mode: 'onSubmit',
    defaultValues: {
      query: isQueryValid ? searchQuery : ''
    }
  });

  const { handleSubmit } = methods;

  const onSubmit: SubmitHandler<ISearchForm> = async (data: ISearchForm) => {
    setActiveArticleId(undefined);
    enableSearchQuery(locale);
    history.push(`${routeList.knowledgeBaseSearchResults}?q=${data.query}`);
  };

  return (
    <FormProvider {...methods}>
      <form onSubmit={handleSubmit(onSubmit)} className="kb-article-search-form">
        <FormActionInput
          className="kb-article-search"
          name="query"
          icon={<Search />}
          maxLength={100}
          validate={validateSearchQuery}
          placeholder={`${messages['knowledge_base_search_placeholder']}`}
        />
      </form>
    </FormProvider>
  );
};

export default ArticleSearchForm;
