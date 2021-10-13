const fs = require('fs');
const hash = require('object-hash');
const path = require('path');

const GUI_ROOT_PATH = path.resolve(__dirname, '..');
const CONFIG_PATH = path.resolve(GUI_ROOT_PATH, '.env.json');
const SCHEMA_PATH = path.resolve(__dirname, 'schema');
const DEFAULT_LOCALE_PATH = path.resolve(__dirname, 'locale');
const DEFAULT_PATH = Object();

const LOCALE_PATH_KEY_NAME = 'LOCALE_PATH';
const API_URL_KEY_NAME = 'REACT_APP_API_URL';
const TOS_KEY_NAME = 'REACT_APP_TOS';

const VERSION_KEY_NAME = 'version';
const LANG_TAGS = ['en', 'pl'];

class ErrorWithCode extends Error {
  constructor(code, ...params) {
    super(...params);
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, ErrorWithCode);
    }
    this.code = code;
  }
}

class ValidationError extends ErrorWithCode {}

class Config {
  constructor(configPath = CONFIG_PATH) {
    this.configPath = configPath;
    this.rawConfig = this.configContent;
    this.config = { ...this.rawConfig };
    if (this.config) {
      this.config['_schema'] = this.configSchema;
    }
  }
  get configContent() {
    try {
      return JSON.parse(fs.readFileSync(this.configPath, 'utf-8'));
    } catch (e) {
      throw new ErrorWithCode(500, `Failed to open the config file (${this.configPath})`);
    }
  }
  get configSchema() {
    let schemaPath = path.resolve(SCHEMA_PATH, 'config.json');
    try {
      return JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
    } catch (e) {
      throw new ErrorWithCode(500, `Cannot open the config schema file: ${schemaPath}`);
    }
  }
  saveConfig(updatedConfigObj) {
    let toSave = {
      ...this.configContent,
      ...updatedConfigObj
    };
    try {
      fs.writeFileSync(this.configPath, JSON.stringify(toSave, null, 2), 'utf-8');
    } catch (e) {
      throw new ErrorWithCode(500, `Failed to update config file: ${e.message}`);
    }
  }
  saveDefaultLocaleToConfig(pathMap, apiUrl) {
    let localeObj = {};
    for (const tag of LANG_TAGS) {
      if (!pathMap[tag]) throw new ErrorWithCode(400, 'Tried to use invalid paths as sources for locale');
    }
    for (const tag of LANG_TAGS) {
      try {
        localeObj[tag] = JSON.parse(fs.readFileSync(pathMap[tag], 'utf-8'));
      } catch (e) {
        throw new ErrorWithCode(500, 'Failed to read default locale files');
      }
    }
    this.saveConfig({
      [TOS_KEY_NAME]: localeObj,
      [LOCALE_PATH_KEY_NAME]: DEFAULT_LOCALE_PATH,
      [API_URL_KEY_NAME]: apiUrl
    });
  }
}

class Locale {
  constructor(config) {
    this.err = null;
    this.config = config;
    this.schemas = this.getSchemas();
    this.locales = undefined;
    this.createdDirs = false;
    this.isDefaultLocale = false;
  }
  getSchemas() {
    let schemaContent = {
      en: {},
      pl: {}
    };
    const schemaPathEn = path.resolve(SCHEMA_PATH, 'en', 'tos.json');
    const schemaPathPl = path.resolve(SCHEMA_PATH, 'pl', 'tos.json');
    const schemaMap = { en: schemaPathEn, pl: schemaPathPl };
    for (const tag in schemaMap) {
      try {
        let content = fs.readFileSync(schemaMap[tag], 'utf8');
        schemaContent[tag] = JSON.parse(content);
      } catch (e) {
        throw new ErrorWithCode(500, `Cannot open the terms of service schema file: ${schemaMap[tag]}`);
      }
    }
    return schemaContent;
  }
  validateLocale(localeObj, schema) {
    for (const key in schema) {
      if (key !== VERSION_KEY_NAME && !localeObj[key]) {
        throw new ValidationError(
          400,
          `The Terms of Service file to be saved does not contain the required ` + `field: ${key} (${schema[key]})`
        );
      }
      if (key === 'terms') {
        this._validateArrayField(localeObj[key], key);
      }
    }
    // check if locale object does not contain additional fields,
    // not included in schema
    let schemaLength = Object.getOwnPropertyNames(schema).length;
    let properLength = localeObj.hasOwnProperty(VERSION_KEY_NAME) ? schemaLength : schemaLength - 1;
    if (Object.getOwnPropertyNames(localeObj).length > properLength) {
      throw new ValidationError(400, 'The Terms of Service file contains some invalid additional fields');
    }
  }
  getDefaultLocale(withSchema = false) {
    let localeObjs = {};
    for (const tag of LANG_TAGS) {
      let currentPath = path.resolve(DEFAULT_LOCALE_PATH, tag, 'tos.json');
      try {
        localeObjs[tag] = JSON.parse(fs.readFileSync(currentPath, 'utf-8'));
      } catch (e) {
        throw new ErrorWithCode(500, `Failed to read default locale file in: ${currentPath}. ${e.message}`);
      }
      if (withSchema) localeObjs[tag]['_schema'] = this.schemas[tag];
    }
    return localeObjs;
  }
  openLocaleFiles(localePath, withSchema = false) {
    const tosPathEn = path.resolve(localePath, 'en', 'tos.json');
    const tosPathPl = path.resolve(localePath, 'pl', 'tos.json');
    let localeContent = {
      en: {},
      pl: {}
    };
    const pathMap = { en: tosPathEn, pl: tosPathPl };
    for (const tag in pathMap) {
      let content = JSON.parse(fs.readFileSync(pathMap[tag], 'utf8'));
      this.validateLocale(content, this.schemas[tag]);
      localeContent[tag] = content;
      if (withSchema) localeContent[tag]['_schema'] = this.schemas[tag];
    }
    return localeContent;
  }
  getLocales() {
    // try to get locale content from JSON files in the path saved
    // saved in config, or get default content from template files
    if (!this.config.config[LOCALE_PATH_KEY_NAME]) {
      throw new ErrorWithCode(
        500,
        `Application config does not have the '${LOCALE_PATH_KEY_NAME}' option. ` +
          `Try to configure the application from the beginning`
      );
    }
    const localePath = this.config.config[LOCALE_PATH_KEY_NAME];
    let warn;
    let localeContent;
    try {
      localeContent = this.openLocaleFiles(localePath, true);
    } catch (e) {
      localeContent = this.getDefaultLocale(true);
      warn =
        `Failed to get locale from ${localePath} (${e.message}).\nContent from template files will be used instead.\n ` +
        `After submitting the form, application will try to save this default content in the chosen location`;
    }
    if (!localeContent) {
      throw new ErrorWithCode(
        500,
        `Cannot open locale files in ${localePath} and failed to parse currently saved locale in the config file. ` +
          `Set a proper path to locale files.`
      );
    }
    if (warn) {
      localeContent['warn'] = warn;
    }
    this.locales = localeContent;
    return localeContent;
  }
  saveLocaleToConfig(localeObjs) {
    let parsedObjs;
    try {
      parsedObjs = JSON.stringify(localeObjs);
    } catch (e) {
      throw new ErrorWithCode(400, 'Failed to parse locale');
    }
    const configUpdate = {
      [TOS_KEY_NAME]: parsedObjs
    };
    this.config.saveConfig(configUpdate);
  }
  createDirs(localePath, createdPaths, langTag) {
    if (!fs.existsSync(localePath)) {
      try {
        fs.mkdirSync(localePath);
        createdPaths.dirs.push(localePath);
        this.createdDirs = true;
      } catch (e) {
        throw new ErrorWithCode(400, `Could not create a directory: ${localePath}`);
      }
    }
    const subdirPath = path.resolve(localePath, langTag);
    if (!fs.existsSync(subdirPath)) {
      try {
        fs.mkdirSync(subdirPath);
        createdPaths[langTag].subDirs.push(subdirPath);
        this.createdDirs = true;
      } catch (e) {
        throw new ErrorWithCode(400, `Could not create a subdirectory: ${subdirPath}`);
      }
    }
    const filePath = path.resolve(subdirPath, 'tos.json');
    try {
      fs.writeFileSync(filePath, '', 'utf-8');
      createdPaths[langTag].files.push(filePath);
    } catch (e) {
      throw new ErrorWithCode(400, `Could not save a file: ${filePath}`);
    }
  }
  saveEditedLocale(localePath, reqBody) {
    // save locale edited in the /saveLocale view
    if (!reqBody['en'] || !reqBody['pl']) throw new ErrorWithCode(400, 'Invalid request');
    this._saveLocale(reqBody, localePath);
  }
  openAndSaveNewLocale(localePath) {
    let localeObjs;
    if (localePath === DEFAULT_PATH) {
      localePath = DEFAULT_LOCALE_PATH;
      localeObjs = this.getDefaultLocale(false);
      this.isDefaultLocale = true;
    } else {
      try {
        localeObjs = this.openLocaleFiles(localePath, false);
      } catch (e) {
        if (e instanceof ValidationError) {
          throw new ErrorWithCode(
            e.code,
            `\nLocale files could not be validated. ${e.message}\n` +
              `Fix your locale files or remove them, so the application can create template files`
          );
        }
        localeObjs = this.getDefaultLocale(false);
        this.isDefaultLocale = true;
      }
    }
    try {
      this._saveLocale(localeObjs, localePath);
    } catch (e) {
      throw new ErrorWithCode(400, e.message);
    }
  }
  cleanDirs(createdPaths) {
    try {
      for (const tag of LANG_TAGS) {
        for (const f of createdPaths[tag].files) {
          // using the function instead of `rmSync()`, because
          // the `rmSync()` has been added in relatively new
          // Node.js version
          fs.unlinkSync(f);
        }
        for (const subDir of createdPaths[tag].subDirs) {
          fs.rmdirSync(subDir);
        }
      }
      for (const dir of createdPaths.dirs) {
        fs.rmdirSync(dir);
      }
    } catch (e) {
      console.warn(`Error during cleanup (${e.message})`);
    }
  }
  setVersion(obj, lang) {
    delete obj['version'];
    let contentHash = hash(obj);
    let dtPart = this._getUTCDateTimeString();
    obj['version'] = `${dtPart}.${lang.toUpperCase()}.${contentHash}`;
    console.log(`New version has been set for the ${lang} ToS file`);
  }

  _saveLocale(fetchedLocaleObjs, localePath) {
    let localeObjs = {};
    let createdPaths = {
      dirs: [],
      en: {
        files: [],
        subDirs: []
      },
      pl: {
        files: [],
        subDirs: []
      }
    };
    try {
      for (const tag of LANG_TAGS) {
        localeObjs[tag] = fetchedLocaleObjs[tag];
        this.validateLocale(localeObjs[tag], this.schemas[tag]);
        if (!this.isDefaultLocale) {
          // do not set new version on default locale content
          try {
            this.setVersion(localeObjs[tag], tag);
          } catch (e) {
            throw new Error(`Failed to generate the version of the Terms of Service file: ${localePath}`);
          }
        }
        let destPath = path.resolve(localePath, tag, 'tos.json');
        try {
          fs.accessSync(destPath, fs.constants.W_OK);
        } catch (e) {
          if (!fs.existsSync(destPath)) {
            try {
              this.createDirs(localePath, createdPaths, tag);
            } catch (e) {
              throw new ErrorWithCode(400, `Cannot save changes to: ${localePath}\n${e.message}`);
            }
          } else {
            throw new ErrorWithCode(
              400,
              `Cannot save changes to: ${localePath}.\nThe path: ${destPath} exists but is not ` + `writable`
            );
          }
        }
      }
      for (const tag of LANG_TAGS) {
        let destPath = path.resolve(localePath, tag, 'tos.json');
        try {
          fs.writeFileSync(destPath, JSON.stringify(localeObjs[tag], null, 2), 'utf-8');
        } catch (e) {
          throw new ErrorWithCode(400, `Failed to save changes to: ${destPath}. ${e.message}`);
        }
      }
      this.saveLocaleToConfig(localeObjs);
    } catch (e) {
      this.cleanDirs(createdPaths);
      throw e;
    }
  }

  _validateArrayField(arr, fieldName) {
    if (!arr.every((i) => i))
      throw new ValidationError(400, `The multi-valued field: ${fieldName} contains empty subfields`);
  }

  _getUTCDateTimeString() {
    let dt = new Date();
    let year = dt.getUTCFullYear();
    // `getMonth()` returns zero-based number - for january it is 0
    let month = this._getPaddedNumber(dt.getUTCMonth() + 1);
    let day = this._getPaddedNumber(dt.getUTCDate());
    let hours = this._getPaddedNumber(dt.getUTCHours());
    let minutes = this._getPaddedNumber(dt.getUTCMinutes());
    return `${year}${month}${day}.${hours}${minutes}`;
  }

  _getPaddedNumber(value) {
    return value < 10 ? `0${value}` : value.toString();
  }
}

module.exports = {
  DEFAULT_PATH: DEFAULT_PATH,
  Config: Config,
  Locale: Locale
};
