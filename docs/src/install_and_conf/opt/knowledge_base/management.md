# Content Management

The administrators of a particular instance of _n6_ are responsible for managing the knowledge base contents (adding, updating, deleting articles and chapters etc...). The aim of this guide section is to describe how the knowledge base structure is built and how to manage articles within that structure.

## _Knowledge Base_ filesystem structure

Articles are stored as a markdown files in a dedicated filesystem structure (see [Initialization and Configuration](config.md)). Current structure assumes that one article is representated as two markdown files, in Polish and English version. Analogicaly one chapter has in structure two physical representations, Polish and English.

Below you will find detailed description of the structure and minimal conditions ensuring its correctness.

### Structure description

1. _Knowledge Base_ filesystem structure has two subfolders, representing the language (`pl` and `en`). Each of them must have the same structure (number of subfolders and articles located in it).
2. Language subfolders contains file `_title.txt`, defining the name of the table of contents in aprioriate language, visible for user in _n6_ GUI.
3. Language subfolders also contains subfolders, which are chapters storing particular articles.  
    The name of chapter subfolder has specific syntax: `id-name`, where:  
    - `id`: identifier of the chapter (unique from the whole knowledge base structure perspective), the number between `1` and `999999`,  
    - `name`: the name of chapter, number or ASCII char (only small letters or chars `-_.`)
4. Chapter subfolders contains file `_title.txt`, defining the name of the chapter, visible for the user in _n6_ GUI.
5. Chapter subfolders also contains article files.  
    The name of article file, anlogicaly to chapter, has specific syntax: `id-name.md`, where:  
    - `id`: identifier of the article (unique from the whole knowledge base structure perspective), the number between `1` and `999999`,  
    - `name`: the name of article, number or ASCII char (only small letters or chars `-_.`)

    The title of the article, visible for user in _n6_ GUI, is taken from the **first line of the article** (after clipping `#` chars and white spaces from the beginning and the end of the line).

#### Example of the knowledge base structure with two chapters and three articles

        knowledge_base/
        ├── en
        │   ├── 10-example-of-chapter-1
        │   │   ├── 10-example-of-article-1.md
        │   │   ├── 20-example-of-article-2.md
        │   │   └── _title.txt
        │   ├── 20-example-of-chapter-2
        │   │   ├── 30-example-of-article-3.md
        │   │   └── _title.txt
        │   └── _title.txt
        └── pl
            ├── 10-przykladowy-rozdzial-1
            │   ├── 10-przykladowy-artykul-1.md
            │   ├── 20-przykladowy-artykul-2.md
            │   └── _title.txt
            ├── 20-przykladowy-rozdzial-2
            │   ├── 30-przykladowy-artykul-3.md
            │   └── _title.txt
            └── _title.txt

### Correctness of the structure - minimal boundary conditions

Below you fill find the minimal boundary conditions for correct knowledge base structure (otherwise user ater click in _Knowledge base_ link will not get table of contents).

1. The depth of the structure is correct (between 1 and 3).
2. Every language directory has file `_title.txt`.
3. Every chapter has file `_title.txt`.
4. Chapters and articles have correct identifiers (natural number between 1 and 999999).
5. Chapters and articles have correct names (number or ASCII char, only small letters or chars `-_.`).
6. Chapter and article identifiers are unique in the given language branch.
7. Chapter and article identifiers are equal among language branches.

## Operations on the _Knowledge Base_
Backend API builds and memoizes _Knowledge Base_ structure data (including documents indexing for the searching purpuse) during the first run of the _n6 Portal_. So after every operation described below, you need to reload the HTTP server. When the typical Apache configuration is in use (so that no Python code is run until a request is obtained), it is recommended to send a client request to trigger the aforementioned _Knowledge Base_ structure data building and memoization; to do so, you can use e.g. the `curl` tool:

    $ cd ~/certs
    $ curl --cert cert.pem --key key.pem -k 'https://localhost/api/info'

### Add chapter

To add new chapter you neeed to:
1. create subfolder with unique identifier, in every language branch,
2. create in chapter subfolder the file `_title.txt` with the title of the chapter displaying in _n6_ GUI. Please consider using max 30 chars for better displaying it in _n6_ GUI.

The identifier is used to sort chapters in table of contents visible for user in _n6_ GUI. It is advisable to create new identifiers with gaps, for example every tenth number for better managing it in the future.

### Update chapter

To update chapter just update the name of the apriopriate chapter subfolders in every language branch. If you want to update the chapter title, you need to update the file `_title.txt`.

### Delete chapter

To delete chapter delete apriopriate chapter subfolders in every language branch. Please remember, then you also delete the content of the chapter (all articles located in it).

### Set the chapter order

For set the right order of the chapter, you need to set the rignt identifier accordingly to your needs. Chapters are visible in the table of contents of the _n6_ GUI in accordance with their identifiers (ascending).

### Add article

To add article you need to know, in which chapter it should be located. In chosen chapter subfolders in every language branch, create markdown file with unique identifier in its name.

First line of the article is the title visible for the user in _n6_ GUI (after clipping `#` chars and white spaces from the beginning and the end of the line). Please consider using max 80 chars for better displaying it in _n6_ GUI.

The identifier is used to sort articles in table of contents visible for user in _n6_ GUI. It is advisable to create new identifiers with gaps, for example every tenth number for better managing it in the future.

### Update article

To update article just update markdown files in article in wanted language branch.

### Delete article

To delete article, delete particular markdown files representing article, in every language branch.

### Set the article order

For set the right order of the article in given chapter, you need to set the rignt identifier accordingly to your needs. Articles are visible in the table of contents of the _n6_ GUI in accordance with their identifiers (ascending).

### Move the article to another chapter

To move an article to another chapter, move the article file to the subfolder representing that chapter (in all language branches).