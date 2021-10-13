const express = require('express');
const path = require('path');
const app = express();
const host = '0.0.0.0';
const port = 3001;
const { DEFAULT_PATH, Config, Locale } = require('./config_app');

const DEFAULT_LOCALE_PATH = path.resolve(__dirname, 'locale');

const LOCALE_PATH_KEY_NAME = 'LOCALE_PATH';
const API_URL_KEY_NAME = 'REACT_APP_API_URL';

app.set('view engine', 'pug');
app.set('views', path.resolve(__dirname, 'views'));

app.use(express.json());
app.use(express.static(path.resolve(__dirname, 'static')));

// helpers
function simpleValidatePath(localePath) {
  return localePath.startsWith('/');
}

app.get('/', (req, res) => {
  res.render('index');
});

app.get('/terms', (req, res) => {
  res.render('terms');
});

app.get('/getConfig', (req, res) => {
  let config;
  try {
    config = new Config();
  } catch (e) {
    res.status(e.code).send(e.message);
    return;
  }
  res.set('Content-Type', 'application/json');
  res.send(config.config);
});

app.get('/getLocale', (req, res) => {
  let config;
  let locale;
  try {
    config = new Config();
    locale = new Locale(config);
    locale.getLocales();
  } catch (e) {
    res.set('Content-Type', 'application/json');
    res.status(e.code).send({ error: e.message });
    return;
  }
  res.set('Content-Type', 'application/json');
  res.send(locale.locales);
});

app.post('/saveConfig', (req, res) => {
  if (req.body) {
    if (!req.body[API_URL_KEY_NAME]) {
      res.status(400).send('Invalid value of the API URL');
      return;
    }
    let config;
    let locale;
    let apiUrl = req.body[API_URL_KEY_NAME].trim();
    let localePath = req.body[LOCALE_PATH_KEY_NAME].trim();
    try {
      config = new Config();
      locale = new Locale(config);
    } catch (e) {
      res.status(e.code).send(e.message);
      return;
    }
    if (!localePath) {
      // empty path - set default path as a locale path
      localePath = DEFAULT_LOCALE_PATH;
    } else if (!simpleValidatePath(localePath)) {
      res.status(400).send('Invalid format of path. It has to be an absolute path (starting with "/")');
      return;
    }
    try {
      locale.openAndSaveNewLocale(localePath === DEFAULT_LOCALE_PATH ? DEFAULT_PATH : localePath);
    } catch (e) {
      res.status(e.code).send(`Failed to save configuration. ${e.message}`);
      return;
    }
    try {
      config.saveConfig({
        [API_URL_KEY_NAME]: apiUrl,
        [LOCALE_PATH_KEY_NAME]: localePath
      });
    } catch (e) {
      res.status(e.code).send(e.message);
      return;
    }
    let msg = 'Configuration has been successfully saved.';
    if (localePath === DEFAULT_LOCALE_PATH) {
      msg += `\nThe location: ${localePath} for locale files has been used, ` + `which is the default location.`;
    } else {
      msg += `\nThe location: ${localePath} for locale files has been used.`;
    }
    if (locale.isDefaultLocale) {
      msg +=
        `\nThe location did not provide proper locale files, so the template content has been saved ` +
        `as locale content.`;
      if (locale.createdDirs) msg += `\nThe proper directory structure has been created in the chosen location.`;
    }
    res.send(msg);
  } else {
    // no request body
    res.status(400).send('Invalid request');
  }
});

app.post('/saveLocale', (req, res) => {
  if (req.body) {
    let config;
    let locale;
    try {
      config = new Config();
      locale = new Locale(config);
      locale.saveEditedLocale(config.config[LOCALE_PATH_KEY_NAME], req.body);
    } catch (e) {
      res.set('Content-Type', 'application/json');
      res.status(e.code).send(e.message);
      return;
    }
    res.send(`Changes to locale files have been saved in:\n${config.config[LOCALE_PATH_KEY_NAME]}`);
  } else {
    res.status(400).send('Invalid request');
  }
});

app.listen(port, host, () => {
  console.log(`The configuration web application is running at http://${host}:${port}`);
});
