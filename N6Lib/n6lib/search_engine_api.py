# Copyright (c) 2022 NASK. All rights reserved.

"""
The module provides functionality of searching any text through
given documents.

The class `SearchEngine` provides method `search()` for searching
any text through indexed previously documents, represented by
the objects of the class `SearchedDocument`. The result of searching
is the list of identifiers of documents, which contain wanted
search phrase. The parameter `search_type` allows to change the type
of searching.

Index can be created by using the method `index_document()` or by setting
the `index` property of the class `SearchEngine`. If index is not set
during searching, the class `SearchEngine` raises  exception
`SearchEngineError`.

Helper class `Analyzer` provides method `analyze()` for creating "tokens"
from the given text. The constructor of the class specifies the parameter
`lang` which is the language in which the given text is analyzing. In
case of not supported language or not specified "stopwords" for the
language, class `Analyzer` raises exception `AnalyzerError`.

Example of use:
>>> se = SearchEngine("pl")
>>> se.index_document(SearchedDocument(1, "tekst dokumentu"))
>>> result = se.search("dokument")

Module is inspired by the article
https://bart.degoe.de/building-a-full-text-search-engine-150-lines-of-code/
"""

import re
from dataclasses import dataclass

import Stemmer
from stempel import StempelStemmer

from n6lib.log_helpers import get_logger


LOGGER = get_logger(__name__)


@dataclass
class SearchedDocument():
    """The class representing searched document."""

    id: int
    content: str

    @property
    def fulltext(self) -> str:
        """
        Get document full text for future searching.

        In the case of more fields defined in the class, we can
        specify in the property the full text for seaching,
        for example `' '.join([self.title, self.content])`
        """
        return self.content


class AnalyzerError(Exception):
    """To be raised on text analysis operation failures."""


class Analyzer:
    """
    The class provides analysis method for the given text.

    The constructor takes an obligatory argument `lang` which is the
    language of the text analysis.

    At the moment supported languages are Polish and English.
    """

    def __init__(self, lang: str) -> None:
        self.lang = lang

    def analyze(self, text: str) -> list[str]:
        """
        Analyse text given in the parameter `text`.

        Returns the list of tokens (individual words after splitting
        the given text) with aplied on them filters. The filters order
        is important because stopwords are not to be stemmed.

        """
        text = self._remove_soft_hyphens(text)
        tokens = self._tokenize(text)
        tokens = self._lowercase_filter(tokens)
        tokens = self._punctuation_filter(tokens)
        tokens = self._stopword_filter(tokens)
        tokens = self._empty_token_filter(tokens)
        tokens = self._stem_filter(tokens)   # stemming must be at the end
        return [token for token in tokens if token]

    #
    # internal methods

    @staticmethod
    def _remove_soft_hyphens(text: str) -> str:
        """Remove soft hyphens from the text."""
        return text.replace("\xad", "")

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split text into tokens."""
        return text.split()

    @staticmethod
    def _lowercase_filter(tokens: list[str]) -> list[str]:
        """Apply lowercase on tokens."""
        return [token.lower() for token in tokens]

    @staticmethod
    def _punctuation_filter(tokens: list[str]) -> list[str]:
        """Remove tokens which are punctuation."""
        punctuation = re.compile(r"[\W_]+")
        return [punctuation.sub("", token) for token in tokens]

    def _stopword_filter(self, tokens: list[str]) -> list[str]:
        """Remove worthless tokens (most popular words)."""
        stopwords = self._get_stopwords()
        return [token for token in tokens if token not in stopwords]

    @staticmethod
    def _empty_token_filter(tokens: list[str]) -> list[str]:
        """Remove empty tokens."""
        return [token for token in tokens if token]

    def _stem_filter(self, tokens: list[str]) -> list[str]:
        """
        Apply stemming on tokens.

        In case of not supported language raise `AnalyzerError`.
        """
        if self.lang == "pl":
            stemmer = StempelStemmer.default()
            return [stemmer.stem(token) for token in tokens]
        if self.lang == "en":
            stemmer = Stemmer.Stemmer("english")
            return [stemmer.stemWord(token) for token in tokens]
        raise AnalyzerError(f"stemmer not found, language {self.lang!a} is not supported")

    def _get_stopwords(self) -> frozenset[str]:
        """
        Get stopwords (worthless tokens) for stopword filter.

        In case of lack of stopwords for the given language
        raise `AnalyzerError`.
        Link to stopwords definitions: https://www.ranks.nl/stopwords
        """
        stopwords = {
            "en": frozenset({
                "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
                "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
                "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
                "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
                "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
                "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
                "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
                "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's",
                "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
                "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
                "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
                "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
                "that", "that's", "the", "their", "theirs", "them", "themselves", "then",
                "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
                "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
                "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what",
                "what's", "when", "when's", "where", "where's", "which", "while", "who",
                "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you",
                "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
            }),
            "pl": frozenset({
                "ach", "aj", "albo", "bardzo", "bez", "bo", "być", "ci", "cię", "ciebie", "co",
                "czy", "daleko", "dla", "dlaczego", "dlatego", "do", "dobrze", "dokąd", "dość",
                "dużo", "dwa", "dwaj", "dwie", "dwoje", "dziś", "dzisiaj", "gdyby", "gdzie",
                "go", "ich", "ile", "im", "inny", "ja", "ją", "jak", "jakby", "jaki", "je",
                "jeden", "jedna", "jedno", "jego", "jej", "jemu", "jeśli", "jest", "jestem",
                "jeżeli", "już", "każdy", "kiedy", "kierunku", "kto", "ku", "lub", "ma", "mają",
                "mam", "mi", "mną", "mnie", "moi", "mój", "moja", "moje", "może", "mu", "my",
                "na", "nam", "nami", "nas", "nasi", "nasz", "nasza", "nasze", "natychmiast",
                "nią", "nic", "nich", "nie", "niego", "niej", "niemu", "nigdy", "nim", "nimi",
                "niż", "obok", "od", "około", "on", "ona", "one", "oni", "ono", "owszem", "po",
                "pod", "ponieważ", "przed", "przedtem", "są", "sam", "sama", "się", "skąd",
                "tak", "taki", "tam", "ten", "to", "tobą", "tobie", "tu", "tutaj", "twoi",
                "twój", "twoja", "twoje", "ty", "wam", "wami", "was", "wasi", "wasz", "wasza",
                "wasze", "we", "więc", "wszystko", "wtedy", "wy", "żaden", "zawsze", "że",
            }),
        }
        if self.lang not in stopwords:
            raise AnalyzerError(f"stopwords for language {self.lang!a} not specified")
        return stopwords[self.lang]


class SearchEngineError(Exception):
    """To be raised on searching operation failures."""


class SearchEngine(Analyzer):
    """
    The class provides searching functionality based on `Analyzer`.

    The constructor takes an obligatory argument `lang` for the
    `Analyzer` purpose.

    Before applying search an index property must be set.
    """

    def __init__(self, lang: str) -> None:
        super().__init__(lang)
        self._index = {}

    @property
    def index(self) -> dict[str, list[int]]:
        return self._index

    @index.setter
    def index(self, new_index: dict[str, list[int]]) -> None:
        """Set new index if you have it prepared earlier."""
        if not isinstance(new_index, dict):
            raise TypeError("index must be a dict")
        for value in new_index.values():
            if not isinstance(value, list):
                raise TypeError("index item's value must be a list")
        self._index = new_index

    @index.deleter
    def index(self) -> None:
        self._index = {}

    def index_document(self, document: SearchedDocument) -> None:
        """Add new document to index."""
        index = self._index
        doc_id = document.id
        for token in self.analyze(document.fulltext):
            token_doc_ids = index.get(token)
            if token_doc_ids is None:
                index[token] = token_doc_ids = []
            if doc_id not in token_doc_ids:
                token_doc_ids.append(doc_id)

    def search(self, query: str, search_type: str = "AND") -> list[int]:
        """
        Search given `query` in given `search_type` among indexed
        documents.
        """
        if not self._index:
            raise SearchEngineError("index not set")

        analyzed_query = self.analyze(query)
        hits = [set(self._index.get(token, [])) for token in analyzed_query]

        if search_type == "AND":
            return list(set.intersection(*hits))
        if search_type == "OR":
            return list(set.union(*hits))
        raise SearchEngineError(f"search type {search_type!a} not allowed")
