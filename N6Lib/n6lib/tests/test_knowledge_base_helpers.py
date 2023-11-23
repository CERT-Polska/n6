# Copyright (c) 2021-2023 NASK. All rights reserved.

import contextlib
import os
import os.path as osp
import shutil
import unittest
from unittest.mock import patch

import pytest
from unittest_expander import (
    expand,
    foreach,
    param,
)

from n6lib.pyramid_commons.knowledge_base_helpers import (
    KnowledgeBaseDataError,
    build_knowledge_base_data,
    get_article_or_chapter_id,
    get_structure_errors,
    read_dir_with_subdirs,
)


@expand
class TestGetArticleOrChapterId(unittest.TestCase):

    @foreach(
        param(
            obj_path="somepath/2-legal_chars.md",
            expected_id=2,
        ).label("correct article name"),
        param(
            obj_path="somepath/2-illegal-Capital-Letters.md",
            expected_id=-1,
        ).label("illegal capital letters"),
        param(
            obj_path="somepath/999999-max-number.md",
            expected_id=999999,
        ).label("correct with max number"),
        param(
            obj_path="somepath/1000000-too_long-number.md",
            expected_id=-1,
        ).label("too long id"),
        param(
            obj_path="somepath/a1-not-a-number.md",
            expected_id=-1,
        ).label("id is not a number"),
        param(
            obj_path="somepath/lack_of_dash.md",
            expected_id=-1,
        ).label("lack of dash"),
        param(
            obj_path="somepath/10-lack-of-md-extension",
            expected_id=-1,
        ).label("lack of '.md' extension"),
        param(
            obj_path="somepath/10-incorrect-extension.jpg",
            expected_id=-1,
        ).label("incorrect extension"),
        param(
            obj_path="somepath/0-illegal_zero_id.md",
            expected_id=-1,
        ).label("illegal zero id"),
    )
    def test_article_identifier(self, obj_path, expected_id):
        with patch("os.path.isfile", return_value=True):
            self.assertEqual(get_article_or_chapter_id(obj_path), expected_id)

    @foreach(
        param(
            obj_path="somepath/2-legal_chars.with.dots",
            expected_id=2,
        ).label("correct chapter name"),
        param(
            obj_path="somepath/2-illegal-Capital-Letters.md",
            expected_id=-1,
        ).label("illegal capital letters"),
        param(
            obj_path="somepath/999999-max-number",
            expected_id=999999,
        ).label("correct max id"),
        param(
            obj_path="somepath/1000000-too_long-number",
            expected_id=-1,
        ).label("too long id"),
        param(
            obj_path="somepath/a1-not-a-number",
            expected_id=-1,
        ).label("id is not a number"),
        param(
            obj_path="somepath/lack_of_dash",
            expected_id=-1,
        ).label("lack of dash"),
        param(
            obj_path="somepath/0-illegal_zero_id",
            expected_id=-1,
        ).label("illegal zero id"),
    )
    def test_chapter_identifier(self, obj_path, expected_id):
        with patch("os.path.isdir", return_value=True):
            self.assertEqual(get_article_or_chapter_id(obj_path), expected_id)


class TestReadDirWithSubdirs(unittest.TestCase):

    def test_read_dir_with_subdirs(self):
        with self._temporary_kb_filesystem() as temp_kb_path:
            structure_elements = read_dir_with_subdirs(
                temp_kb_path,
                root=temp_kb_path,
                output_data={},
            )

        self.assertIsInstance(structure_elements, dict)
        self.assertEqual(structure_elements.keys(), {1, 2, 3})
        for i in range(1,3):
            self.assertIsInstance(structure_elements[i], list)
        self.assertEqual(
            sorted(structure_elements[1]),
            [
                {"content": "",
                 "parent_name": "",
                 "name": "pl",
                 "parent_id": -1,
                 "path": f"{temp_kb_path}pl",
                 "type": "",
                 "id": -1,
                 "lang": "pl",
                },
            ],
        )
        self.assertEqual(
            sorted(structure_elements[2], key=lambda x:x["name"]),
            [
                {"content": "",
                 "parent_name": "pl",
                 "name": "10-rozdzial",
                 "parent_id": -1,
                 "path": f"{temp_kb_path}pl/10-rozdzial",
                 "type": "chapter",
                 "id": 10,
                 "lang": "pl",
                },
                {"content": "Spis treści",
                 "parent_name": "pl",
                 "name": "_title.txt",
                 "parent_id": -1,
                 "path": f"{temp_kb_path}pl/_title.txt",
                 "type": "title",
                 "id": -1,
                 "lang": "pl",
                },
            ],
        )
        self.assertEqual(
            sorted(structure_elements[3], key=lambda x:x["name"]),
            [
                {"content": "## Artykuł\nTreść artykułu",
                 "parent_name": "10-rozdzial",
                 "name": "10-artykul.md",
                 "parent_id": 10,
                 "path": f"{temp_kb_path}pl/10-rozdzial/10-artykul.md",
                 "type": "article",
                 "id": 10,
                 "lang": "pl",
                },
                {"content": "Rozdział",
                 "parent_name": "10-rozdzial",
                 "name": "_title.txt",
                 "parent_id": 10,
                 "path": f"{temp_kb_path}pl/10-rozdzial/_title.txt",
                 "type": "title",
                 "id": -1,
                 "lang": "pl",
                },
            ],
        )

    @staticmethod
    @contextlib.contextmanager
    def _temporary_kb_filesystem() -> str:
        temp_kb_path = osp.join(osp.dirname(__file__), "test_kb_structure/")
        if not osp.isdir(temp_kb_path):
            _create_directory(temp_kb_path)
            pl_branch = osp.join(temp_kb_path, "pl/")
            _create_directory(pl_branch)
            pl_chapter = osp.join(pl_branch, "10-rozdzial/")
            _create_directory(pl_chapter)
            pl_branch_titlefile = osp.join(pl_branch, "_title.txt")
            _create_file(pl_branch_titlefile, "Spis treści")
            pl_article = osp.join(pl_chapter, "10-artykul.md")
            _create_file(pl_article, "## Artykuł\nTreść artykułu")
            pl_chapter_titlefile = osp.join(pl_chapter, "_title.txt")
            _create_file(pl_chapter_titlefile, "Rozdział")
        try:
            yield str(temp_kb_path)
        except Exception as exc:
            print(exc)
        finally:
            shutil.rmtree(temp_kb_path)


class TestGetStructureErrors(unittest.TestCase):

    def test_errors_correct_structure(self):
        structure = _get_read_dir_with_subdirs_output()
        self.assertEqual(get_structure_errors(structure), [])

    def test_errors_added_subdirectories(self):
        structure = _get_read_dir_with_subdirs_output(added_subdirectories=True)
        self.assertEqual(
            get_structure_errors(structure),
            ["Wrong depth of the structure: 4, must be between 1 and 3"],
        )

    def test_errors_removed_title_file_in_branch(self):
        structure = _get_read_dir_with_subdirs_output(removed_titlefile_in_pl_branch=True)
        self.assertEqual(
            get_structure_errors(structure),
            ["No title file in every language directory"],
        )

    def test_errors_removed_title_file_in_chapter(self):
        structure = _get_read_dir_with_subdirs_output(removed_titlefile_in_pl_chapter=True)
        self.assertEqual(
            get_structure_errors(structure),
            ["No title file in every chapter directory"],
        )

    def test_errors_wrong_chapter_identifier(self):
        structure = _get_read_dir_with_subdirs_output(
            en_first_chapter_filename="-1-wrong identifier",
            pl_first_chapter_filename="-1-wrong identifier",
        )
        self.assertEqual(get_structure_errors(structure), ["Wrong chapter identifier"])

    def test_errors_wrong_article_identifier(self):
        structure = _get_read_dir_with_subdirs_output(
            en_first_article_filename="-1-wrong identifier",
            pl_first_article_filename="-1-wrong identifier",
        )
        self.assertEqual(get_structure_errors(structure), ["Wrong article identifier"])

    def test_errors_not_unique_chapter_identifiers(self):
        structure = _get_read_dir_with_subdirs_output(
            en_first_chapter_filename="10-filename",
            en_second_chapter_filename="10-filename",
            pl_first_chapter_filename="10-nazwa pliku",
            pl_second_chapter_filename="10-nazwa pliku",
        )
        self.assertEqual(get_structure_errors(structure), ["Not unique chapter identifier"])

    def test_errors_not_unique_article_identifiers(self):
        structure = _get_read_dir_with_subdirs_output(
            en_first_article_filename="10-filename",
            en_second_article_filename="10-filename",
            pl_first_article_filename="10-nazwa pliku",
            pl_second_article_filename="10-nazwa pliku",
        )
        self.assertEqual(get_structure_errors(structure), ["Not unique article identifier"])

    def test_errors_not_consistent_chapter_identifiers_between_branches(self):
        structure = _get_read_dir_with_subdirs_output(en_first_chapter_filename="999-filename")
        self.assertEqual(
            get_structure_errors(structure),
            ["Missing chapter identifiers in other language"],
        )

    def test_errors_not_consistent_article_identifiers_between_branches(self):
        structure = _get_read_dir_with_subdirs_output(en_first_article_filename="999-filename")
        self.assertEqual(
            get_structure_errors(structure),
            ["Missing article identifiers in other language"],
        )

    def test_errors_removed_branch(self):
        structure = _get_read_dir_with_subdirs_output(removed_pl_branch=True)
        self.assertEqual(
            set(get_structure_errors(structure)),
            set([
                "Missing chapter identifiers in other language",
                "Missing article identifiers in other language",
            ]),
        )

    def test_errors_removed_chapter(self):
        structure = _get_read_dir_with_subdirs_output(removed_second_chapter_in_pl_branch=True)
        self.assertEqual(
            set(get_structure_errors(structure)),
            set([
                "Missing chapter identifiers in other language",
                "Missing article identifiers in other language",
            ]),
        )

    def test_errors_removed_article(self):
        structure = _get_read_dir_with_subdirs_output(removed_second_article_in_pl_branch=True)
        self.assertEqual(
            get_structure_errors(structure),
            ["Missing article identifiers in other language"],
        )


class TestBuildKnowledgeBaseData(unittest.TestCase):

    @pytest.mark.slow
    def test_build_kb_data_correct_structure(self):
        with patch(
            "n6lib.pyramid_commons.knowledge_base_helpers.read_dir_with_subdirs",
            return_value=_get_read_dir_with_subdirs_output(),
        ):
            result = build_knowledge_base_data("somepath")
            self.assertIsInstance(result, dict)
            self.assertEqual(result.keys(), {"table_of_contents", "articles", "index"})
            self.assertIsInstance(result["table_of_contents"], dict)
            self.assertEqual(result["table_of_contents"].keys(), {"title", "chapters"})
            self.assertIsInstance(result["articles"], dict)
            self.assertEqual(len(result["articles"]), 2)
            self.assertIsInstance(result["index"], dict)
            languages = {"pl", "en"}
            self.assertEqual(result["index"].keys(), languages)
            for lang in languages:
                self.assertIsInstance(result["index"][lang], dict)

    def test_build_kb_data_structure_errors(self):
        with patch(
            "n6lib.pyramid_commons.knowledge_base_helpers.get_structure_errors",
            return_value=["first error", "second error"],
        ):
            with patch(
                "n6lib.pyramid_commons.knowledge_base_helpers.read_dir_with_subdirs",
                return_value=_get_read_dir_with_subdirs_output(),
            ):
                with self.assertRaises(KnowledgeBaseDataError) as context:
                    build_knowledge_base_data("somepath")
                self.assertEqual(
                    "errors in knowledge base structure (first error; second error)",
                    str(context.exception),
                )


#
# Helper functions

def _get_read_dir_with_subdirs_output(
    knowledge_base_path: str = "somepath",

    pl_first_chapter_filename: str = "2-nowosci",
    en_first_chapter_filename: str = "2-news",
    pl_second_chapter_filename: str = "200-cyberbezpieczenstwo",
    en_second_chapter_filename: str = "200-cybersecurity",

    pl_first_article_filename: str = "5-nowe-funkcje-w-n6.md",
    en_first_article_filename: str = "5-new-functions.md",
    pl_second_article_filename: str = "15-najczestsze-ataki.md",
    en_second_article_filename: str = "15-common-hacker-attacks.md",

    removed_pl_branch: bool = False,
    removed_titlefile_in_pl_branch: bool = False,
    removed_second_chapter_in_pl_branch: bool = False,
    removed_titlefile_in_pl_chapter: bool = False,
    removed_second_article_in_pl_branch: bool = False,
    added_subdirectories: bool = False,
) -> dict:
    """Get knowledge base structure (the output of the function
    `read_dir_with_subdirs`) with path given in parameter
    `knowledge_base_path` and with parameters defining the structure
    (separately for pl and en branch).

    We assume to build the structure with two branches (pl end en),
    in which there are a title file and two chapters with one article
    file and title file.

    There is also the posibility to add subdirectories for checking
    incorrect depth of the structure, and add third article in one
    branch for checking inconsistency between branches.
    """

    structure = {
        1: [
            {
                "content": "",
                "parent_name": "",
                "name": "en",
                "parent_id": -1,
                "path": f"{knowledge_base_path}/en",
                "type": "",
                "id": -1,
                "lang": "en",
            },
        ],
        2: [
            {
                "content": "Table of contents",
                "parent_name": "en",
                "name": "_title.txt",
                "parent_id": -1,
                "path": f"{knowledge_base_path}/en/_title.txt",
                "type": "title",
                "id": -1,
                "lang": "en",
            },
            {
                "content": "",
                "parent_name": "en",
                "name": en_first_chapter_filename,
                "parent_id": -1,
                "path": f"{knowledge_base_path}/en/{en_first_chapter_filename}",
                "type": "chapter",
                "id": _get_id(en_first_chapter_filename),
                "lang": "en",
            },
            {
                "content": "",
                "parent_name": "en",
                "name": en_second_chapter_filename,
                "parent_id": -1,
                "path": f"{knowledge_base_path}/en/{en_second_chapter_filename}",
                "type": "chapter",
                "id": _get_id(en_second_chapter_filename),
                "lang": "en",
            },
        ],
        3: [
            {
                "content": "News",
                "parent_name": en_first_chapter_filename,
                "name": "_title.txt",
                "parent_id": _get_id(en_first_chapter_filename),
                "path": f"{knowledge_base_path}/en/{en_first_chapter_filename}/_title.txt",
                "type": "title",
                "id": -1,
                "lang": "en",
            },
            {
                "content": "Cybersecurity",
                "parent_name": en_second_chapter_filename,
                "name": "_title.txt",
                "parent_id": _get_id(en_second_chapter_filename),
                "path": f"{knowledge_base_path}/en/{en_second_chapter_filename}/_title.txt",
                "type": "title",
                "id": -1,
                "lang": "en",
            },
            {
                "content": f"# **Title {en_first_article_filename}**\nfree text\n",
                "parent_name": en_first_chapter_filename,
                "name": en_first_article_filename,
                "parent_id": _get_id(en_first_chapter_filename),
                "path": f"{knowledge_base_path}/en/"
                        f"{en_first_chapter_filename}/{en_first_article_filename}",
                "type": "article",
                "id": _get_id(en_first_article_filename),
                "lang": "en",
            },
            {
                "content": f"# **Title {en_second_article_filename}**\nfree text\n",
                "parent_name": en_second_chapter_filename,
                "name": en_second_article_filename,
                "parent_id": _get_id(en_second_chapter_filename),
                "path": f"{knowledge_base_path}/en/"
                        f"{en_second_chapter_filename}/{en_second_article_filename}",
                "type": "article",
                "id": _get_id(en_second_article_filename),
                "lang": "en",
            },
        ],
    }

    if added_subdirectories:
        third_chapter_id = _get_id(en_first_chapter_filename) + _get_id(en_second_chapter_filename)
        third_chapter_name = f"{third_chapter_id}-third_chapter_filename"
        structure[3].append({
            "content": "",
            "parent_name": en_first_chapter_filename,
            "name": third_chapter_name,
            "parent_id": -1,
            "path": f"{knowledge_base_path}/en/{en_first_chapter_filename}/{third_chapter_name}",
            "type": "chapter",
            "id": third_chapter_id,
            "lang": "en",
        })
        third_article_id = _get_id(en_first_article_filename) + _get_id(en_second_article_filename)
        third_article_name = f"{third_article_id}-third_article_filename"
        structure[4] = {
            "content": f"# **Title {third_article_name}**\nfree text\n",
            "parent_name": third_chapter_name,
            "name": third_article_name,
            "parent_id": third_chapter_id,
            "path": f"{knowledge_base_path}/en/{en_first_chapter_filename}"
                    f"{third_chapter_name}/{third_article_name}",
            "type": "article",
            "id": third_article_id,
            "lang": "en",
        }
    if not removed_pl_branch:
        structure[1].append({
            "content": "",
            "parent_name": "",
            "name": "pl",
            "parent_id": -1,
            "path": f"{knowledge_base_path}/pl",
            "type": "",
            "id": -1,
            "lang": "pl",
        })
        structure[2].append({
            "content": "",
            "parent_name": "pl",
            "name": pl_first_chapter_filename,
            "parent_id": -1,
            "path": f"{knowledge_base_path}/pl/{pl_first_chapter_filename}",
            "type": "chapter",
            "id": _get_id(pl_first_chapter_filename),
            "lang": "pl",
        })
        structure[3].append({
            "content": "Nowości",
            "parent_name": pl_first_chapter_filename,
            "name": "_title.txt",
            "parent_id": _get_id(pl_first_chapter_filename),
            "path": f"{knowledge_base_path}/en/{pl_first_chapter_filename}/_title.txt",
            "type": "title",
            "id": -1,
            "lang": "pl",
        })
        structure[3].append({
            "content": f"# **Tytul {pl_first_article_filename}**\nfree text\n",
            "parent_name": pl_first_chapter_filename,
            "name": pl_first_article_filename,
            "parent_id": _get_id(pl_first_chapter_filename),
            "path": f"{knowledge_base_path}/pl/"
                    f"{pl_first_chapter_filename}/{pl_first_article_filename}",
            "type": "article",
            "id": _get_id(pl_first_article_filename),
            "lang": "pl",
        })
        if not removed_titlefile_in_pl_branch:
            structure[2].append({
                "content": "",
                "parent_name": "",
                "name": "pl",
                "parent_id": -1,
                "path": f"{knowledge_base_path}/pl/_title.txt",
                "type": "title",
                "id": -1,
                "lang": "pl",
            })
        if not removed_second_chapter_in_pl_branch:
            structure[2].append({
                "content": "",
                "parent_name": "pl",
                "name": pl_second_chapter_filename,
                "parent_id": -1,
                "path": f"{knowledge_base_path}/pl/{pl_second_chapter_filename}",
                "type": "chapter",
                "id": _get_id(pl_second_chapter_filename),
                "lang": "pl",
            })
            if not removed_titlefile_in_pl_chapter:
                structure[3].append({
                    "content": "Cyberbezpieczeństwo",
                    "parent_name": pl_second_chapter_filename,
                    "name": "_title.txt",
                    "parent_id": _get_id(pl_second_chapter_filename),
                    "path": f"{knowledge_base_path}/en/{pl_second_chapter_filename}/_title.txt",
                    "type": "title",
                    "id": -1,
                    "lang": "pl",
                })
            if not removed_second_article_in_pl_branch:
                structure[3].append({
                    "content": f"# **Title {pl_second_article_filename}**\nfree text\n",
                    "parent_name": pl_second_chapter_filename,
                    "name": pl_second_article_filename,
                    "parent_id": _get_id(en_second_chapter_filename),
                    "path": f"{knowledge_base_path}/en/"
                            f"{pl_second_chapter_filename}/{pl_second_article_filename}",
                    "type": "article",
                    "id": _get_id(pl_second_article_filename),
                    "lang": "pl",
                })
    return structure

def _get_id(name: str) -> int:
    """Get identifier from the given name (assuming, that the given
    name corresponds to the names of articles and chapters
    so it contains char `-` and first part of the name is the number).
    """
    try:
        return int(name.split("-")[0].strip()) if "-" in name else -1
    except ValueError:
        return -1

def _create_directory(path: osp) -> None:
    """Create directory given in the parameter `path`.
    """
    os.mkdir(path)

def _create_file(path: osp, content: str) -> None:
    """Create file given in the parameter `path`, with the content given
    in the paramerer `content`.
    """
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
