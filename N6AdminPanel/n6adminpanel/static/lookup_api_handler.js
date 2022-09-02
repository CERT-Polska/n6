const POPUP_MAIN_CLASS = 'api_result_popup';
const POPUP_CLASSLIST = [POPUP_MAIN_CLASS, 'well', 'fade-in'];
const POPUP_ERROR_CLASS = 'api_error_popup';
const REQUEST_BTN_CLASS = 'api-lookup-btn';
const REQUEST_BTN_DISABLED_CLASS = 'api-lookup-btn--disabled';
const RELOAD_BTN_CLASSLIST = ['reload-btn', 'btn', 'btn-default'];
const HIDDEN_CLASS = 'hidden';
const EMPTY_VALUE_PLACEHOLDER = '-';

const ASN_RECORD = Symbol('asn');
const FQDN_FROM_EMAIL_RECORD = Symbol('fqdn_from_email');
const FQDN_RECORD = Symbol('fqdn');
const IP_NETWORK_RECORD = Symbol('ip_network');
const FQDN_FROM_EMAIL_VAL_ATTR_NAME = 'data-fqdn-value';
const API_CLIENTS_URL_MAP = {
    [ASN_RECORD]: '/ripe/asn',
    [FQDN_FROM_EMAIL_RECORD]: '/baddomains/domain',
    [FQDN_RECORD]: '/baddomains/domain',
    [IP_NETWORK_RECORD]: '/ripe/ip_network',
};

const ASN_CACHE = {};
const FQDN_CACHE = {};
const IP_NETWORK_CACHE = {};


class PopupBase {

    // The class is meant as an abstract base class. Its subclasses
    // handle different types of records.

    value;

    constructor(parentNode) {
        this.parentNode = parentNode;
        this.requestBtn = this.parentNode.querySelector(`.${REQUEST_BTN_CLASS}`);
        this.popup = this._getPopupBase();
        this.spinner = this._getSpinner();
    }

    get headerText() {
        throw new Error('The `headerText` getter must be implemented in the subclass');
    }

    get recordType() {
        throw new Error('The `recordType` getter must be implemented in the subclass');
    }

    get recordLabel() {
        throw new Error('The `recordLabel` getter must be implemented in the subclass');
    }

    get popupIconClass() {
        throw new Error('The `popupIconClass` getter must be implemented in the subclass');
    }

    get resultCacheObj() {
        throw new Error('The `resultCacheObj` getter must be implemented in the subclass');
    }

    get resultCache() {
        throw new Error('The `resultCache` getter must be implemented in the subclass');
    }

    set resultCache(data) {
        throw new Error('The `resultCache` getter must be implemented in the subclass');
    }

    async getResponse(value) {
        throw new Error('The `getResponse()` method must be implemented in the subclass');
    }

    _buildResultTable(data) {
        // Abstract method called from `this._buildResultPopup()`.
        // It has to be implemented in the concrete subclass.
        throw new Error('The `_buildResultTable()` method must be implemented in the subclass');
    }

    showSpinner() {
        this.requestBtn.classList.add(HIDDEN_CLASS);
        this.parentNode.appendChild(this.spinner);
    }

    hideSpinner() {
        this.spinner.remove();
        this.requestBtn.classList.remove(HIDDEN_CLASS);
    }

    showResult(data) {
        // cache results to avoid downloading it on every click
        // of the lookup button
        this.resultCache = data;
        this._buildResultPopup(data);
        this._switchBtnToClose();
        this.parentNode.appendChild(this.popup);
    }

    showError(msg) {
        this._switchBtnToClose();
        const errHeader = document.createElement('h3');
        errHeader.textContent = 'Error';
        const msgText = document.createElement('p');
        msgText.textContent = msg;
        this.popup.appendChild(errHeader);
        this.popup.appendChild(msgText);
        this.popup.classList.add(POPUP_ERROR_CLASS);
        this.parentNode.appendChild(this.popup);
    }

    _getPopupBase() {
        const popup = document.createElement('div');
        POPUP_CLASSLIST.forEach(val => {
          popup.classList.add(val);
        });
        const img = document.createElement('div');
        img.classList.add(this.popupIconClass);
        const header = document.createElement('h1');
        header.textContent = this.headerText;
        const reloadBtn = document.createElement('button');
        reloadBtn.type = 'button';
        RELOAD_BTN_CLASSLIST.forEach(c => {
          reloadBtn.classList.add(c);
        });
        reloadBtn.addEventListener('click', e => {
                // a small hack so the reload button has the same
                // parent element as the request button, so other
                // DOM items are on the same level as if clicking
                // the request button
                const replacedEvent = {
                    target: {
                        parentNode: this.requestBtn.parentNode,
                    },
                };
                delete this.resultCacheObj[this.value];
                handleClose(replacedEvent, this.recordType);
                return makeApiRequest(replacedEvent, this.recordType);
            }, false);
        this.mainHeader = document.createElement('legend');
        this.mainHeader.appendChild(reloadBtn);
        this.mainHeader.appendChild(header);
        popup.appendChild(img);
        popup.appendChild(this.mainHeader);
        return popup;
    }

    _switchBtnToClose() {
        this.requestBtn.onclick = (e) => handleClose(e, this.recordType);
        this.requestBtn.classList.add(REQUEST_BTN_DISABLED_CLASS);
    }

    _getSpinner() {
        const container = document.createElement('div');
        container.classList.add('spinner');
        container.classList.add('el-over-input');
        Array.from(Array(3)).forEach((_, i) => {
            const div = document.createElement('div');
            div.classList.add(`bounce${i+1}`);
            container.appendChild(div);
        });
        return container;
    }

    _buildResultPopup(data) {
        // if the `value` has been set, add a subheader with its value
        if (this.value) {
            const subHeader = document.createElement('h2');
            subHeader.textContent = `${this.recordLabel}: ${this.value}`;
            this.mainHeader.appendChild(subHeader);
        }
        this._buildResultTable(data);
    }

    _getRowArrayContentOrNull(val) {
        if (Array.isArray(val) && val.length) {
            const rows = [];
            val.forEach(i => {
                const innerRow = document.createElement('p');
                innerRow.textContent = typeof i === 'string' && !i ? EMPTY_VALUE_PLACEHOLDER : i;
                rows.push(innerRow);
            });
            return rows;
        }
        return null;
    }
}


class RipePopupBase extends PopupBase {

    get headerText() {
        return 'RIPE API Lookup Result';
    }

    async getResponse(value) {
        return fetch(_getUrlWithParams(value, this.recordType))
            .then(response => {
                if (!response.ok) {
                    throw new Error(response.status === 400
                        ? 'Invalid value of the request parameter'
                        : 'Failed to get a proper network response');
                }
                return response.json()
                    .catch(() => {
                        throw new Error('Failed to parse a JSON response');
                    });
            });
    }

    _buildResultTable(data) {
        // the script requests only one value at the time from RIPE API
        // client, so the first item of result list is being handled
        const resultList = this._getListsOfSeparatePersonData(data[0]);
        // every item of `resultList` will be used to create separate table
        for (const result of resultList) {
            const resultTable = document.createElement('table');
            this.popup.appendChild(resultTable);
            for (const item of result) {
                const [key, val] = item;
                const row = document.createElement('tr');
                const label = document.createElement('th');
                const rowValue = document.createElement('td');
                label.textContent = key || EMPTY_VALUE_PLACEHOLDER;
                const innerRows = this._getRowArrayContentOrNull(val);
                if (innerRows) {
                    innerRows.forEach(i => {
                        rowValue.appendChild(i);
                    });
                } else {
                    rowValue.textContent = EMPTY_VALUE_PLACEHOLDER;
                }
                row.appendChild(label);
                row.appendChild(rowValue);
                resultTable.appendChild(row);
            }
        }
    }

    _getListsOfSeparatePersonData(items) {
        const resultList = [];
        let currentList = [];
        resultList.push(currentList);
        for (const item of items) {
            const [key, val] = item;
            // single list-item containing both empty strings serves
            // as a separator between each result set
            if (!key && !val) {
                if (currentList.length) resultList.push(currentList);
                currentList = [];
            } else {
                // each item of the new list will be a 2-element list,
                // where its first item is a key, and second - a list
                // of values; there will be no key duplicates
                const elIndex = currentList.findIndex(el => el[0] === key);
                const valList = Array.isArray(val) ? val : [val];
                if (elIndex !== -1) {
                    currentList[elIndex][1].push(...valList);
                } else {
                    currentList.push([key, valList]);
                }
            }
        }
        return resultList;
    }
}


class ASNPopup extends RipePopupBase {

    get recordType() {
        return ASN_RECORD;
    }

    get recordLabel() {
        return 'ASN';
    }

    get popupIconClass() {
        return 'asn-results-icon';
    }

    get resultCacheObj() {
        return ASN_CACHE;
    }

    get resultCache() {
        return ASN_CACHE[this.value];
    }

    set resultCache(data) {
        ASN_CACHE[this.value] = data;
    }
}


class IPNetworkPopup extends RipePopupBase {

    get recordType() {
        return IP_NETWORK_RECORD;
    }

    get recordLabel() {
        return 'IP Network';
    }

    get popupIconClass() {
        return 'ip-net-results-icon';
    }

    get resultCacheObj() {
        return IP_NETWORK_CACHE;
    }

    get resultCache() {
        return this.resultCacheObj[this.value];
    }

    set resultCache(data) {
        IP_NETWORK_CACHE[this.value] = data;
    }
}


class FQDNPopup extends PopupBase {

    ExtendedError = class ExtendedError extends Error {
        constructor(args) {
            const {msg, stage} = args;
            super(msg);
            // override the `message` property, so the `showError()`
            // method will be passed an object instead of a string
            this.message = {message: msg, stage: stage};
        }
    }

    async getResponse(value) {
        return fetch(_getUrlWithParams(value, this.recordType))
            .catch(() => {
                throw this.ExtendedError({msg: 'Connection error'});
            })
            .then(response => {
                return response.json()
                    .catch(err => {
                        // invalid JSON response
                        if (response.ok) throw new this.ExtendedError(
                            {msg: 'Failed to parse a JSON response'});
                        // request has failed and the response does
                        // not contain a JSON with error details
                        throw new this.ExtendedError(
                            {msg: this._getErrorMsgBasedOnStatus(response.status)});
                    })
                    .then(data => {
                        if (!response.ok) {
                            // request has failed but the response
                            // contains a JSON with error details
                            throw new this.ExtendedError(data);
                        }
                        // request has succeeded
                        return data;
                });
            });
    }

    showError(msgObj) {
        const {message, stage} = msgObj;
        this._switchBtnToClose();
        const errHeader = document.createElement('h3');
        errHeader.textContent = 'Error';
        const msgText = document.createElement('p');
        msgText.textContent = message;
        this.popup.appendChild(errHeader);
        if (stage) {
            const subHeader = this._createErrSubHeader(stage);
            this.popup.appendChild(subHeader);
        }
        this.popup.appendChild(msgText);
        this.popup.classList.add(POPUP_ERROR_CLASS);
        this.parentNode.appendChild(this.popup);
    }

    _getErrorMsgBasedOnStatus(statusCode) {
        switch (statusCode) {
            case 400:
                return 'Failed to validate the requested value';
            case 403:
                return 'Unauthorized request';
            case 404:
                return 'The requested value was not found';
            case 500:
                return 'Internal server error';
            case 503:
                return 'Service unavailable';
            default:
                return 'Failed to get a proper network response';
        }
    }

    _createErrSubHeader(stage) {
        let txt = 'There was an error during the '
        switch (stage) {
            case 'auth':
                txt +=  'authentication stage';
                break;
            case 'contact_uid':
                txt += 'fetching of the "contact_uid"';
                break;
            case 'client_details':
                txt += 'fetching of the results';
                break;
            default:
                txt += 'unspecified stage';
        }
        const el = document.createElement('h4');
        el.textContent = txt;
        return el;
    }

    _buildResultTable(data) {
        const resultTable = document.createElement('table');
        this.popup.appendChild(resultTable);
        for (const key in data) {
            const row = document.createElement('tr');
            const label = document.createElement('th');
            const rowValue = document.createElement('td');
            label.textContent = key || EMPTY_VALUE_PLACEHOLDER;
            const innerRows = this._getRowArrayContentOrNull(data[key]);
            if (innerRows) {
                innerRows.forEach(i => {
                    rowValue.appendChild(i);
                });
            } else {
                rowValue.textContent = typeof data[key] === 'string' && !data[key] ?
                    EMPTY_VALUE_PLACEHOLDER : data[key];
            }
            row.appendChild(label);
            row.appendChild(rowValue);
            resultTable.appendChild(row);
        }
    }

    get headerText() {
        return 'Baddomains API Lookup Result';
    }

    get recordType() {
        return FQDN_RECORD;
    }

    get recordLabel() {
        return 'FQDN';
    }

    get popupIconClass() {
        return 'fqdn-results-icon';
    }

    get resultCacheObj() {
        return FQDN_CACHE;
    }

    get resultCache() {
        return FQDN_CACHE[this.value];
    }

    set resultCache(data) {
        FQDN_CACHE[this.value] = data;
    }
}


// event handlers

async function makeApiRequest(e, recordType) {
    const parentNode = e.target.parentNode;
    let popupInst;
    if (recordType === ASN_RECORD) {
        popupInst = new ASNPopup(parentNode);
    } else if (recordType === IP_NETWORK_RECORD) {
        popupInst = new IPNetworkPopup(parentNode);
    } else if (recordType === FQDN_RECORD || recordType === FQDN_FROM_EMAIL_RECORD) {
        popupInst = new FQDNPopup(parentNode);
    } else {
        throw new Error(`Unknown type of record`);
    }
    popupInst.showSpinner();
    try {
        let value = _getValue(parentNode, recordType);
        popupInst.value = value;
        try {
            let data;
            // try to retrieve cached response data
            data = popupInst.resultCache;
            if (!data) data = await popupInst.getResponse(value);
            if (Object.keys(data).length) {
                popupInst.showResult(data);
            } else {
                throw new Error('The response is empty');
            }
        } catch (err) {
            popupInst.showError(err.message);
        }
    } catch (err) {
        popupInst.showError(err.message);
    } finally {
        popupInst.hideSpinner();
        delete popupInst;
    }
}

function handleClose(e, recordType) {
    const parentNode = e.target.parentNode;
    const popup = parentNode.querySelector(`.${POPUP_MAIN_CLASS}`);
    _fadeOut(popup);
    _switchBtnToOpen(parentNode, recordType);
    popup.remove();
}


// helper functions

function _getValue(parentNode, recordType=null) {
    let value;
    let emptyValueErrMsg = 'The field has no value';
    const input = parentNode.querySelector('input.form-control');
    if (!input) throw new Error('Could not locate the input element');
    if (recordType === FQDN_FROM_EMAIL_RECORD) {
        value = input.getAttribute(FQDN_FROM_EMAIL_VAL_ATTR_NAME);
        emptyValueErrMsg += ' or a domain name could not be extracted from the e-mail address';
    } else {
        value = input.value;
    }
    if (!value) throw new Error(emptyValueErrMsg);
    return value;
}

function _getUrlWithParams(paramValue, recordType) {
    const baseUrl = API_CLIENTS_URL_MAP[recordType];
    if (!baseUrl) throw new Error('Cannot establish an API URL for this type of record');
    const searchParams = new URLSearchParams({value: paramValue});
    return `${baseUrl}?${searchParams}`;
}

function _switchBtnToOpen(parentNode, recordType) {
    const btn = parentNode.querySelector(`.${REQUEST_BTN_CLASS}`);
    btn.onclick = (e) => makeApiRequest(e, recordType);
    btn.classList.remove(REQUEST_BTN_DISABLED_CLASS);
}

function _fadeOut(el) {
    el.classList.remove('fade-in');
    el.classList.add('fade-out');
}
