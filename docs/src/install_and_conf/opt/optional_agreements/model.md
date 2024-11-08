# The *Agreement* model

## Overview

_Agreements_ are managed as objects stored in _Auth DB_. Those objects may be viewed, added, edited and deleted [using the Admin Panel](manage.md).

## _Agreement_'s fields

- `label` (string, **required**) – **primary key**, a string value; it may also be used to briefly describe this agreement for the *n6* instance's administrators.
- `en` (string, **required**) – the English description of the agreement as seen in the [Registration](portal.md#registration-form) and [Organization Agreements](portal.md#organization-agreements-menu) forms. Limited to 255 characters.
- `pl` (string, **required**) – the Polish description of the agreement as seen in the [Registration](portal.md#registration-form) and [Organization Agreements](portal.md#organization-agreements-menu) forms. Limited to 255 characters.
- `url_en` (string, optional) – a link (URL) to an external website (a [**See more**](portal.md#registration-form) hyperlink) with additional information for this agreement when English language is used. This link must use the HTTP or HTTPS protocol.
- `url_pl` (string, optional) – a link (URL) to an external website (a [**See more**](portal.md#registration-form) hyperlink) with additional information for this agreement when Polish language is used. This link must use the HTTP or HTTPS protocol.
- `default_consent` (boolean, default=True) – a flag used to determine if this agreement should be marked by default in the Registration form.

## _Agreement_'s relations

_Agreement_ as an _Auth DB_ model exists independently of other models, so its instances are not deleted by cascade when a related object is being removed. There are two _Auth DB_ models in relation with _Agreement_:

- _Org_ – agreements related with an _Org_ are binding for the organization and can be managed client-side using the [*Organization Agreements*](portal.md) menu in *n6 Portal*. **If an `Agreement` is in the _Org_'s `agreements` list, it means the organization accepted to it**.
- _RegistrationRequest_ – during registration, it is possible to check or un-check each of available agreements, so when a _RegistrationRequest_ is accepted by an administrator, a new _Org_ is immediately created with the checked agreements.
