# Copyright (c) 2022-2023 NASK. All rights reserved.

import unittest

import pytest
from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.search_engine_api import (
    Analyzer,
    AnalyzerError,
    SearchedDocument,
    SearchEngine,
    SearchEngineError,
)


@expand
class TestAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = Analyzer("pl")

    @foreach([
        param(lang="pl", query="; Nowego, tEstu. ", result=["nówy", "test"]),
        param(lang="en", query="; Newly, tEsted. ", result=["newli", "test"]),
    ])
    def test_analyze_correct(self, lang, query, result):
        self.analyzer.lang = lang
        analyzed_query = self.analyzer.analyze(query)
        self.assertEqual(analyzed_query, result)

    @foreach("de", "-", "")
    def test__stopword_filter_error_lack_of_stopwords(self, lang):
        self.analyzer.lang = lang
        with self.assertRaises(AnalyzerError) as context:
            self.analyzer._stopword_filter(["test"])        
        self.assertEqual(
            f"stopwords for language '{lang}' not specified",
            str(context.exception),
        )

    @foreach("de","-", "")
    def test__stem_filter_error_not_supported_language(self, lang):
        self.analyzer.lang = lang
        with self.assertRaises(AnalyzerError) as context:
            self.analyzer._stem_filter(["test"])
        self.assertEqual(
            f"stemmer not found, language '{lang}' is not supported",
            str(context.exception),
        )


@expand
class TestSearcheEngine(unittest.TestCase):

    def setUp(self):
        self.search_engine = SearchEngine("pl")

    def test_set_index_correct(self):
        new_index = {
            "token1": [1, 2, 3],
            "token2": [1, 2],
        }
        self.assertEqual(self.search_engine.index, {})
        self.search_engine.index = new_index
        self.assertEqual(self.search_engine.index, new_index)

    @foreach(
        "token",
        1,
        ["token", 1],
    )
    def test_set_index_error_not_dict(self, wrong_index):
        with self.assertRaises(TypeError) as context:
            self.search_engine.index = wrong_index
        self.assertEqual(
            "index must be a dict",
            str(context.exception),
        )

    @foreach(
        {"token": 1},
        {"token": "text"},
        {"token": {1, 2}},
        {"token": (1, 2)},
    )
    def test_set_index_error_not_list_in_dict(self, wrong_index):
        with self.assertRaises(TypeError) as context:
            self.search_engine.index = wrong_index
        self.assertEqual(
            "index item's value must be a list",
            str(context.exception),
        )

    @pytest.mark.slow
    def test_index_document_correct(self):
        self.assertEqual(self.search_engine.index, {})
        document_1 = SearchedDocument(1, "zawartość dokumentu")
        self.search_engine.index_document(document_1)
        self.assertEqual(
            self.search_engine.index,
            {
                "zawartość": [1],
                "dokument": [1]
            },
        )
        document_2 = SearchedDocument(2, "zawartość artykułu")
        self.search_engine.index_document(document_2)
        self.assertEqual(
            self.search_engine.index,
            {
                "zawartość": [1, 2],
                "dokument": [1],
                "artykuł": [2]
            },
        )

    @pytest.mark.slow
    def test_search_correct(self):
        for document in [SearchedDocument(1, "zawartość dokumentu"),
                         SearchedDocument(2, "zawartość artykułu")]:
            self.search_engine.index_document(document)
        self.assertEqual(self.search_engine.search("ARTYKUŁOWI"), [2])
        self.assertEqual(self.search_engine.search("Zawartości"), [1, 2])
        self.assertEqual(self.search_engine.search("Zawartości Dokumentu"), [1])
        self.assertEqual(self.search_engine.search("Zawartości Dokumentu", "OR"), [1, 2])

    def test_search_error_index_not_set(self):
        with self.assertRaises(SearchEngineError) as context:
            self.search_engine.search("dokument")
        self.assertEqual("index not set", str(context.exception))

    @pytest.mark.slow
    def test_search_error_wrong_search_type(self):
        with self.assertRaises(SearchEngineError) as context:
            self.search_engine.index_document(SearchedDocument(1, "dokument"))
            wrong_search_type = "ALL"
            self.search_engine.search("dokument", wrong_search_type)
        self.assertEqual(
            f"search type '{wrong_search_type}' not allowed",
            str(context.exception),
        )
