# _n6 Portal_ Backend API

When it comes to the *knowledge base*, the *n6 Portal*'s backend API provides the following endpoints:
* *Table of Contents* (`GET /knowledge_base/contents`),
* *Article* (`GET /knowledge_base/articles/<article_id>`),
* *Search* (`GET /knowledge_base/search`).

HTTP responses of the endpoints are strictly dependent on switching on/off the *knowledge base* (see [Initialization and   Configuration](config.md)).

## The *Table of Contents* endpoint

URL: `/knowledge_base/contents`  
Description: getting the table of contents of the knowledge base (for logged in user)  
Methods: `GET`  
Authentication required: yes  
Parameters: none  
Posible HTTP responses:
- **200 OK** - table of contents in JSON format
- **403 Forbidden** - client is *not* authenticated
- **404 Not Found** - client is authenticated but *knowledge base* is switched off
- **500 Internal Server Error** - error in backend API, also in case of incorrect *knowledge base* structure when it is switched on (see section "Correctnes of the structure - minimal boundary conditions" in [Content Management](management.md))

### Example output

```json
{
    "title": {
        "pl": "Spis artykułów",
        "en": "Table of contents" 
    },
    "chapters": [
        {
            "id": 10,
            "title": {
                "pl": "Nowości",
                "en": "News" 
            },
            "articles": [
                {
                    "id": 10,
                    "url": "/knowledge_base/articles/10",
                    "title": {
                        "pl": "Nowe funkcje w n6",
                        "en": "New functions in n6" 
                    }
                },
                {
                    "id": 20,
                    "url": "/knowledge_base/articles/20",
                    "title": {
                        "pl": "Migracja do nowej wersji Pythona",
                        "en": "Migration to a new Python version" 
                    }
                }
            ]
        },
        {
            "id": 20,
            "title": {
                "pl": "Cyberbezpieczeństwo",
                "en": "Cybersecurity" 
            },
            "articles": [
                {
                    "id": 30,
                    "url": "/knowledge_base/articles/30",
                    "title": {
                        "pl": "Najczęstsze ataki",
                        "en": "Most frequent attacks" 
                    }
                }
            ]
        }
    ]
}
```

## The *Article* endpoint

URL: `/knowledge_base/articles/<article_id>`  
Description: getting fixed article in all language versions (for logged in user)  
Methods: `GET`  
Authentication required: yes  
Parameters: none  
Posible HTTP responses:
- **200 OK** - article with identifier `article_id` in JSON format
- **403 Forbidden** - client is *not* authenticated
- **404 Not Found** - client is authenticated but article with identifier `article_id` cannot be found or *knowledge base* is switched off
- **500 Internal Server Error** - error in backend API

### Example output

```json
{
    "id": 10,
    "chapter_id": 10,
    "content": {
        "pl": "# **Nowe funkcje w n6**\nTekst o nowych funkcjach w n6\n",
        "en": "# **New functions**\nText about new functions in n6\n\n"
    }
}
```

## The *Search* endpoint

URL: `/knowledge_base/search`  
Description: getting the subset of the table of contents with articles which contain at least one of the word from the search phrase (for logged in user)  
Methods: `GET`  
Authentication required: yes  
Parameters:
- **lang** - language of the searching (posible values: `pl`, `en`)
- **q** - search phrase (any characters except new line indicator, with total length between 3 and 100 chars)

Posible HTTP responses:
- **200 OK** - subset of the table of contents in JSON format
- **400 Bad Request** - wrong or missing parameters in HTTP request
- **403 Forbidden** - client is *not* authenticated
- **404 Not Found** - client is authenticated but *knowledge base* is switched off
- **500 Internal Server Error** - error in backend API, also in case of incorrect *knowledge base* structure when it is switched on (see section "Correctnes of the structure - minimal boundary conditions" in [Content Management](management.md))

### Example output

```json
{
    "title": {
        "pl": "Spis artykułów",
        "en": "Table of contents" 
    },
    "chapters": [
        {
            "id": 20,
            "title": {
                "pl": "Cyberbezpieczeństwo",
                "en": "Cybersecurity" 
            },
            "articles": [
                {
                    "id": 30,
                    "url": "/knowledge_base/articles/30",
                    "title": {
                        "pl": "Najczęstsze ataki",
                        "en": "Most frequent attacks" 
                    }
                }
            ]
        }
    ]
}
```
