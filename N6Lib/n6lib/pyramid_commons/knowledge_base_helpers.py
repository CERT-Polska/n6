# Copyright (c) 2021-2022 NASK. All rights reserved.

"""
Package prepares data for the Portal API in the case of
the knowledge base data.

The structure of the output data of the main function
`build_knowledge_base_data` is a dictionary with three keys:
1. "table_of_contents" - output data for the API endpoint
   `GET /knowledge_base/contents`, dictionary containing:
   - "title": title of the table of content in Polish and English version
   - "chapters": chapter objects of the table of content, containing:
      * "id": unique identifier of the chapter
      * "title": title of the chapter in Polish and English version
      * "articles": list of article objects, containing:
         -- "id": unique identifier of the article
         -- "url": url to the article
         -- "title": title of the article in Polish and English version
2. "articles" - all articles for output data for the API endpoint
   `GET /knowledge_base/articles/<article_id>`, dictionary containing:
   - "<article_id>": article object containing:
      * "id": unique identifier of the article
      * "chapter_id": unique identifier of the chapter
      * "content": the content of the article in Polish and English
        version
3. "index" - indexed articles for the searching functionality for
   the API endpoint `GET /knowledge_base/search`, dictionary containing:
   - "pl": a Polish index, a dictionary containing:
      * "<token>": list of identifiers of articles which contain token
   - "en": an English index, a dictionary containing:
      * "<token>": list of identifiers of articles which contain token
"""


import os
import os.path as osp
import re
from copy import deepcopy
from operator import itemgetter

from n6lib.log_helpers import get_logger
from n6lib.search_engine_api import (
    SearchedDocument,
    SearchEngine,
)


LOGGER = get_logger(__name__)

ARTICLE_FILE_RE = re.compile(r"\A([1-9]\d{0,5})-[a-z0-9-_.]+\.md\Z")
CHAPTER_DIR_RE = re.compile(r"\A([1-9]\d{0,5})-[a-z0-9-_.]+\Z")
TITLE_FILE_RE = re.compile(r"\A_title.txt\Z")
SEARCH_PHRASE_RE = re.compile(r"\A.{3,100}\Z")


class KnowledgeBaseDataError(Exception):
    """To be raised on knowledge base data operation failures."""


def build_knowledge_base_data(knowledge_base_path: str) -> dict:
    """
    Build the data for the Portal API endpoints,
    based on the knowledge base directory from the parameter
    `knowledge_base_path`.

    Returns a dictionary with:
    1. table of contents of the articles
    2. all articles with their content
    3. indexed articles for the searching functionality
    """

    structure_elements = read_dir_with_subdirs(
        dir_path=knowledge_base_path,
        root=knowledge_base_path,
        output_data={},
    )

    errors = get_structure_errors(structure_elements)
    if errors:
        LOGGER.error("Errors in knowledge base structure: %a", "; ".join(errors))
        raise KnowledgeBaseDataError(f'errors in knowledge base structure ({"; ".join(errors)})')

    unique_articles = {}
    unique_chapters = []
    # for every chapter build its content (id, title and list of articles)
    for chapter in get_chapters(structure_elements):
        # consider chapter only once
        if is_object_in_objects_list(chapter, unique_chapters):
            continue

        # for every article in the chapter, build its content (id, url and title)
        # and build the list of unique article objects
        unique_articles_in_chapter = []
        for article in get_articles_from_chapter(structure_elements, chapter["id"]):
            # consider article only once
            if is_object_in_objects_list(article, unique_articles_in_chapter):
                continue

            unique_articles_in_chapter.append(
                create_article_obj_for_table_of_contents(
                    structure_elements,
                    article['id'],
                ),
            )
            unique_articles[str(article["id"])] = create_article_obj_for_unique_articles(
                structure_elements,
                article["id"],
                chapter["id"],
            )

        unique_chapters.append(
            create_chapter_obj_for_table_of_contents(
                structure_elements,
                chapter["id"],
                sorted(unique_articles_in_chapter, key=itemgetter("id")),
            ),
        )

    return {
        "table_of_contents": {
            "title": {
                "pl": get_table_of_content_title(structure_elements, "pl"),
                "en": get_table_of_content_title(structure_elements, "en"),
            },
            "chapters": sorted(unique_chapters, key=itemgetter("id")),
        },
        "articles": unique_articles,
        "index": {
            "pl": create_index(unique_articles, "pl"),
            "en": create_index(unique_articles, "en"),
        },
    }


def create_index(articles: dict, lang: str) -> dict:
    """
    Create index for given articles and language."""
    assert isinstance(articles, dict)
    search_engine = SearchEngine(lang)
    for article in articles.values():
        searched_document = SearchedDocument(article["id"], article["content"][lang])
        search_engine.index_document(searched_document)
    return search_engine.index


def is_object_in_objects_list(obj: dict, objects: list) -> bool:
    """
    Check if the identifier of the object given in the parameter
    `obj` is in the list of identifiers of objects from the parameter
    `objects`.
    """
    assert isinstance(obj, dict)
    assert isinstance(objects, list)
    return obj["id"] in {el["id"] for el in objects}


def search_in_knowledge_base(knowledge_base_data: dict, lang: str, search_phrase: str) -> dict:
    """
    Search `search_phrase` in the given `knowledge_base_data` in
    the `lang` branch.
    """
    search_engine = SearchEngine(lang)
    search_engine.index = knowledge_base_data["index"][lang]
    return prepare_search_result(
        table_of_contents=knowledge_base_data["table_of_contents"],
        found_article_ids=set(search_engine.search(search_phrase, "OR")),
    )


def prepare_search_result(table_of_contents: dict, found_article_ids: set) -> dict:
    """
    Prepare subset of the table of contents accordingly to the given
    set of article identifiers.

    Returns subset of the table of contents for the *Portal API*
    `GET /knowledge_base/search` endpoint.
    """
    table_of_contents_copy = deepcopy(table_of_contents)
    for chapter in table_of_contents_copy["chapters"]:
        chapter["articles"] = [
            article for article in chapter["articles"] if article["id"] in found_article_ids
        ]
    table_of_contents_copy["chapters"] = [
        chapter for chapter in table_of_contents_copy["chapters"] if chapter["articles"]
    ]
    return table_of_contents_copy


def read_dir_with_subdirs(dir_path: str, root: str, output_data: dict, lvl: int = 1) -> dict:
    """
    Read recursively data from the `dir_path` through all its
    subdirectories.

    Args:
        `dir_path`:
            The path to the directory in which the function reads data.
        `root`:
            The auxiliary parameter for getting the `lang` attribute of
            the child object (at start the same as `dir_path`).
        `output_data`:
            The dictionary with the structure read by the function,
            consists:
                - `name`: the name of the given object,
                - `parent_name`: the name of the parent of the given
                        object,
                - `path`: the path of the given object,
                - `type`: the type of the given object,
                - `id`: the identifier of the given object (or -1),
                - `parent_id`: the identifier of the parent of the
                        given object,
                - `content`: the content of the given object,
                - `lang`: the language of the given object ("pl"/"en").
        `lvl`:
            The depth of the reading structure (the given `dir_path` is
            the "0" lvl).

    Returns:
        The end value of the `output_data` parameter.
    """

    assert isinstance(output_data, dict)
    if not output_data.get(lvl):
        output_data[lvl] = []

    for child in os.listdir(dir_path):
        child_path = osp.join(dir_path, child)
        child_obj = {
            "name": child,
            "parent_name": osp.split(dir_path)[-1],
            "path": child_path,
            "type": get_object_type(child_path),
            "id": get_article_or_chapter_id(child_path),
            "parent_id": get_article_or_chapter_id(dir_path),
            "content": get_article_or_chapter_title_content(child_path),
            "lang": get_object_lang(child_path, root),
        }

        output_data[lvl].append(child_obj)
        if osp.isdir(child_path):
            read_dir_with_subdirs(child_path, root, output_data, lvl + 1)
    return output_data

#
# Helper functions working on the objects get from the function
# `read_dir_with_subdirs`.

def get_structure_errors(structure_elements: dict) -> list:
    """
    Check if the structure from the function `read_dir_with_subdirs`
    is correct:
        * the depth of the structure is correct (between 1 and 3),
        * every language directory has file `_title.txt`,
        * every chapter has file `_title.txt`,
        * chapters and article have correct identifiers (not `-1`),
        * chapter and article identifiers are unique in the given
          language branch,
        * chapter and article identifiers are equal among language
          branches.

    Returns:
        The list of error messages or empty list in the case of lack
        of errors.
    """
    errors = []

    lvl = get_structure_lvl(structure_elements)
    if  lvl < 1 or lvl > 3:
        errors.append(f"Wrong depth of the structure: {lvl}, must be between 1 and 3")

    chapter_identifiers = [chapter["id"] for chapter in get_chapters(structure_elements)]
    if -1 in chapter_identifiers:
        errors.append("Wrong chapter identifier")

    article_identifiers = [article["id"] for article in get_articles(structure_elements)]
    if -1 in article_identifiers:
        errors.append("Wrong article identifier")

    no_of_language_dirs = len(get_language_dirs(structure_elements))
    no_of_table_of_content_titles = len(get_table_of_content_titles(structure_elements))
    if no_of_language_dirs != no_of_table_of_content_titles:
        errors.append("No title file in every language directory")

    no_of_chapters = len(get_chapters(structure_elements))
    no_of_chapter_titles = len(get_chapter_titles(structure_elements))
    if no_of_chapters != no_of_chapter_titles:
        errors.append("No title file in every chapter directory")

    chapter_identifiers_pl = [chapter["id"] for chapter in get_chapters(structure_elements)
                              if chapter["lang"] == "pl"]
    if sorted(chapter_identifiers_pl) != sorted(list(set(chapter_identifiers_pl))):
        errors.append("Not unique chapter identifier")

    chapter_identifiers_en = [chapter["id"] for chapter in get_chapters(structure_elements)
                              if chapter["lang"] == "en"]
    if sorted(chapter_identifiers_pl) != sorted(chapter_identifiers_en):
        errors.append("Missing chapter identifiers in other language")

    article_identifiers_pl = [article["id"] for article in get_articles(structure_elements)
                              if article["lang"] == "pl"]
    if sorted(article_identifiers_pl) != sorted(list(set(article_identifiers_pl))):
        errors.append("Not unique article identifier")

    article_identifiers_en = [article["id"] for article in get_articles(structure_elements)
                              if article["lang"] == "en"]
    if sorted(article_identifiers_pl) != sorted(article_identifiers_en):
        errors.append("Missing article identifiers in other language")

    return errors


def create_chapter_obj_for_table_of_contents(structure_elements: dict,
                                             chapter_id: int,
                                             chapter_articles: list) -> dict:
    """
    Create the content of the chapter section for the table of contents
    needs, for the chapter with identifier given in parameter `chapter_id`,
    needed for the endpoint `/knowledge_base/contents`.
    """
    return  {
        "id": chapter_id,
        "title": {
            "pl": get_chapter_title(structure_elements, chapter_id, "pl"),
            "en": get_chapter_title(structure_elements, chapter_id, "en"),
        },
        "articles": chapter_articles,
    }


def create_article_obj_for_table_of_contents(structure_elements: dict, article_id: int) -> dict:
    """
    Create the content of the article section for the table of contents
    needs, for the article with identifier given in parameter `article_id`,
    needed for the endpoint `/knowledge_base/contents`.
    """
    return {
        "id": article_id,
        "url": f"/knowledge_base/articles/{article_id}",
        "title": {
            "pl": get_article_title(structure_elements, article_id, "pl"),
            "en": get_article_title(structure_elements, article_id, "en"),
        },
    }


def create_article_obj_for_unique_articles(structure_elements: dict,
                                           article_id: int,
                                           chapter_id: int) -> dict:
    """
    Create the content of the articles needed for the endpoint
    `/knowledge_base/articles/<article_id>`.
    """
    return {
        "id": article_id,
        "chapter_id": chapter_id,
        "content": {
            "pl": get_article_content(structure_elements, article_id, "pl"),
            "en": get_article_content(structure_elements, article_id, "en"),
        },
    }


def get_language_dirs(structure_elements: dict) -> list:
    """
    Get language directories from the objects given in
    the structure from the function `read_dir_with_subdirs`.
    """
    return list(structure_elements[1])


def get_table_of_content_titles(structure_elements: dict) -> list:
    """
    Get titles of the table of content from the objects given in
    the structure from the function `read_dir_with_subdirs`.
    """
    return [el for el in structure_elements[2] if el["type"] == "title"]


def get_table_of_content_title(structure_elements: dict, lang: str) -> list:
    """
    Get the title of the table of content with given in
    parameter `lang` language ("pl"/"en"), based on
    the structure from the function `read_dir_with_subdirs`.
    """
    return [title_file["content"]
            for title_file in get_table_of_content_titles(structure_elements)
            if title_file["lang"] == lang][0]


def get_chapters(structure_elements: dict) -> list:
    """
    Get chapters from the objects given in
    the structure from the function `read_dir_with_subdirs`.
    """
    return [el for el in structure_elements[2] if el["type"] == "chapter"]


def get_chapter_titles(structure_elements: dict) -> list:
    """
    Get chapter titles from the objects given in
    the structure from the function `read_dir_with_subdirs`.
    """
    return [el for el in structure_elements[3] if el["type"] == "title"]


def get_chapter_title(structure_elements: dict, chapter_id: int, lang: str) -> str:
    """
    Get chapter title for chapter identifier given in `chapter_id`
    parameter and language given in `lang` parameter ("pl"/"en").
    """
    return [title_file["content"]
            for title_file in get_chapter_titles(structure_elements)
            if title_file["parent_id"] == chapter_id
                and title_file["lang"] == lang][0]


def get_articles(structure_elements: dict) -> list:
    """
    Get articles from the objects given in
    the structure from the function `read_dir_with_subdirs`.
    """
    return [el for el in structure_elements[3] if el["type"] == "article"]


def get_articles_from_chapter(structure_elements: dict, chapter_id: int) -> list:
    """
    Get articles from the chapter for given parameter `chapter_id`,
    from the objects given in the structure from the function
    `read_dir_with_subdirs`.
    """
    return [article for article in get_articles(structure_elements)
            if article["parent_id"] == chapter_id]


def get_article_content(structure_elements: dict, article_id: int, lang: str) -> str:
    """
    Get the content of the article with identifier given in the
    parameter `article_id`, with the language given in the parameter
    `lang`, from the objects given in the structure from the function
    `read_dir_with_subdirs`.
    """
    return [article["content"] for article in get_articles(structure_elements)
            if article["id"] == article_id
                and article["lang"] == lang][0]


def get_article_title(structure_elements: dict, article_id: int, lang: str) -> str:
    """
    Get article title for article identifier given in `article_id`
    parameter and language given in `lang` parameter ("pl"/"en").
    """
    content = get_article_content(structure_elements, article_id, lang)
    try:
        title = content[:content.index("\n")]
    except ValueError:
        title = content
    return title.strip().lstrip('#').lstrip()


def get_structure_lvl(structure_elements: dict) -> int:
    """
    Get the depth of the structure given in
    the structure from the function `read_dir_with_subdirs`.
    """
    return len(structure_elements.keys())

#
# Helper functions for touching the filesystem for the function
# `read_dir_with_subdirs` needs.

def get_object_type(obj_path: str) -> str:
    """
    Get the type of the given object ("article"/"chapter"/"title"
    or empty string).
    """
    if is_article(obj_path):
        return "article"
    if is_chapter(obj_path):
        return "chapter"
    if is_title_file(obj_path):
        return "title"
    return ""


def get_article_or_chapter_id(obj_path: str) -> int:
    """
    If the object from `obj_path` is article or chapter,
    get the unique identifier.

    Otherwise, return the value -1.
    """
    obj_name = obj_path.split("/")[-1]
    if is_article(obj_path):
        return int(ARTICLE_FILE_RE.search(obj_name).group(1))
    if is_chapter(obj_path):
        return int(CHAPTER_DIR_RE.search(obj_name).group(1))
    return -1


def get_object_lang(obj_path: str, root: str) -> str:
    """
    Get the language of the object from the path of the object,
    given in the parameter `obj_path`. The parameter `root` helps to
    identify the level on which the language can be found.

    If path does not exist, return the empty string.
    """
    path_parts = obj_path.split(root)[1].split("/")
    for path_part in path_parts:
        if path_part in ["pl", "en"]:
            return path_part
    return ""


def get_article_or_chapter_title_content(obj_path: str) -> str:
    """
    If the object from `obj_path` is article or chapter title file,
    get its content.

    Otherwise return the empty string.
    """
    if is_article(obj_path) or is_title_file(obj_path):
        with open(obj_path, "r", encoding="utf-8") as file:
            return file.read()
    return ""


def is_article(path: str) -> bool:
    """
    Check if the object given in the `path` is the article.
    """
    obj_name = path.split("/")[-1]
    return osp.isfile(path) and ARTICLE_FILE_RE.search(obj_name)


def is_chapter(path: str) -> bool:
    """
    Check if the object given in the `path` is the chapter.
    """
    obj_name = path.split("/")[-1]
    return osp.isdir(path) and CHAPTER_DIR_RE.search(obj_name)


def is_title_file(path: str) -> bool:
    """
    Check if the object given in the `path` is the file with the
    chapter title.
    """
    obj_name = path.split("/")[-1]
    return osp.isfile(path) and TITLE_FILE_RE.search(obj_name)
