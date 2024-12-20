# _n6 Portal_ Backend API

With the implementation of _Agreements_, two new endpoints were introduced: `/agreements` and `/org_agreements`, along with some changes to the `/register` endpoint.

## `/agreements`

- Description: returns a list of all agreements and their contents
- Methods: `GET`
- Authentication required: no
- Parameters: none
- Possible HTTP responses:
    - **200 OK** -- _Agreement_ data list (in JSON format)
    - **500 Internal Server Error** -- error in backend API

Example output:

```json
[
  {
    "label": "example_agreement",
    "default_consent": true,
    "en": "This is an english description of this agreement. This description will be shown on N6 Portal.",
    "pl": "To jest polski opis tej zgody. Ten opis będzie wyświetlony na Portalu N6.",
    "url_en": "https://example.website.com",
    "url_pl": "http://przykladowa.strona.pl"
  }
]
```

## `/org_agreements`

- Description: returns a list of labels of the agreements accepted by the organization to which the logged-in user belongs
- Methods: `GET`, `POST`
- Authentication required: yes
- Parameters:
    - `GET` -- none
    - `POST` -- form-data with the key `agreements` (the labels of the agreements user wants to exclusively agree to -- on behalf of their organization).
- Possible HTTP responses:
    - **200 OK** -- list of _Agreement_ labels
    - **403 Forbidden** -- client is _not_ authenticated
    - **500 Internal Server Error** -- error in backend API

Example output (`GET`):

```json
["example_agreement"]
```

Example request data (`POST`):

```json
-----------------------------3242449602272325684267654132
Content-Disposition: form-data; name="agreements"

example_agreement,second_agreement
-----------------------------3242449602272325684267654132--
```

Example response data (`POST`):

```json
["example_agreement", "second_agreement"]
```

## `/register`

With the implementation of _Agreements_, a new field – `agreements` – was added to the *n6 Portal*'s form corresponding to this endpoint. The field receives a list of the labels of the agreements accepted by the client's organization.

```json
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="org_id"

example
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="actual_name"

example
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="email"

example@com.pl
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="submitter_title"

example
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="submitter_firstname_and_surname"

example
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="notification_language"

PL
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="notification_emails"

example@com.pl
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="asns"

1
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="fqdns"

example.com
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="ip_networks"

0.0.0.0/32
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="terms_lang"

EN
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="terms_version"

20230313.1707.EN.bad239ac495eb6185805623ca52d6287f8f1b18d
-----------------------------17310712402843492328469257347
Content-Disposition: form-data; name="agreements"

example_agreement
-----------------------------17310712402843492328469257347--

```
