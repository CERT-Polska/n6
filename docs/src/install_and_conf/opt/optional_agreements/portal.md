# Appearance in _n6 Portal_

## Overview

Introducing Organization _Agreements_ to an _n6_ instance causes minor changes in the _n6 Portal_'s appearance, allowing users to interact with the agreements, i.e., agree or disagree (in the name of the user's organization) to the agreements' terms.

## Registration form

If any agreements have been created, they are shown at the bottom of the second page of the *registration form*. Whether they are checked by default or not is determined by the `default_consent` flag (as per [schema](model.md/#agreement-schema)).

![Registration form agreement](img/registration_form.png)
_Registration form. Notice the **See more** hyperlink which takes the user to `url_en`, in this case `https://example.website.com`. This hyperlink is to be rendered only if the URL for the current language is provided._

## Navigation bar

When at least one agreement is provided, a new navigation bar item becomes available to users: _Organization agreements_.

![Navigation bar](img/navigation_bar.png)
_Navigation bar with additional **Organization agreements** item. This item would not be there if no agreements have been created._

## Organization agreements menu

In **Organization agreements**, all agreements are visible, and users are able to manage their _Org_'s agreements by clicking the checkboxes.

![Organization agreements menu](img/organization_agreements_item.png)
_Organization agreements menu with a single item. Notice that it is not checked as accepted even though it has `default_consent=True`._

If there are no agreements, the URI `/agreements-settings` is not available via the GUI and only a stub page is presented with the information that no agreements are available.

![Organization agreements menu with no items](img/organization_agreements_empty.png)
_Organization agreements menu with a stub message._
