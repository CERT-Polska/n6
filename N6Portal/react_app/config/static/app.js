const inputArrayRe = /\[\d*\]$/;

function setFormListeners() {
  window.onload = getFormData;
  let sendBtn = document.querySelector('#sendBtn');
  sendBtn.addEventListener('click', onSave, false);
  let resetBtn = document.querySelector('#resetBtn');
  resetBtn.addEventListener('click', onReset, false);
}

function showInfoMessage(msg) {
  _showMsg('#infoMsg', msg);
}

function showErrorMsg(msg) {
  _showMsg('#errorMsg', msg);
}

function closeMsgs(e) {
  _clearMsgNode('#infoMsg');
  _clearMsgNode('#errorMsg');
  e.stopPropagation();
  document.querySelector('html').removeEventListener('click', closeMsgs);
}

function makeGetRequest(url) {
  fetch(url, {
    method: 'GET'
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.error) throw new Error(data.error);
      if (data.warn) showInfoMessage(data.warn);
      fillForm(data);
    })
    .catch((e) => {
      showErrorMsg(`Failed to load form data. ${e.message}`);
      console.log(e);
    });
}

function getPayloadFromFormData(formId) {
  let termsForm = document.querySelector(formId);
  return _getObjFromFormData(new FormData(termsForm));
}

function addInputPair(parentNode, label, name, value, elemType = 'input', inputClass = null, readOnly = false) {
  let newLabel = document.createElement('label');
  newLabel.textContent = label;
  let newInput = document.createElement(elemType);
  newInput.name = name;
  newInput.value = value !== undefined ? value : '';
  if (inputClass) newInput.classList.add(inputClass);
  if (readOnly) newInput.setAttribute('readonly', 'readonly');
  parentNode.appendChild(newLabel);
  parentNode.appendChild(newInput);
}

function validateForm(formId) {
  let formNode = document.querySelector(formId);
  let fields = formNode.querySelectorAll('input, textarea');
  for (const field of fields) {
    if (!field) {
      field.classList.add('invalidField');
    } else if (field.classList.contains('invalidField')) {
      field.classList.remove('invalidField');
    }
  }
}

function clearNode(nodeId) {
  let node = document.querySelector(nodeId);
  while (node.firstChild) {
    node.removeChild(node.lastChild);
  }
}

function fillConfigForm(parentNode, data) {
  // return the state of config - is it ready or not
  let configReady = true;
  for (const key in data['_schema']) {
    addInputPair(parentNode, data['_schema'][key], key, data[key]);
    if (!data[key]) {
      // if any field is empty, mark configuration as not ready
      configReady = false;
    }
  }
  return configReady;
}

// helpers

function _showMsg(divId, msg) {
  let el = document.querySelector(divId);
  el.classList.remove('hidden');
  for (const row of msg.split('\n')) {
    let txt = document.createElement('p');
    txt.textContent = row;
    el.appendChild(txt);
  }
  document.querySelector('html').addEventListener('click', closeMsgs, false);
}

function _clearMsgNode(divId) {
  clearNode(divId);
  document.querySelector(divId).classList.add('hidden');
}

function _getObjFromFormData(formData) {
  let obj = {};
  for (const i of formData) {
    let key = i[0];
    // replace array brackets to get array name, if they exist
    let arrayName = key.replace(inputArrayRe, '');
    if (key !== arrayName) {
      // if the condition is true, the key is an array
      if (!obj.hasOwnProperty(arrayName)) obj[arrayName] = [];
      obj[arrayName].push(i[1]);
    } else {
      obj[key] = i[1];
    }
  }
  return obj;
}
