import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App, { keycloak } from 'App';
// import reportWebVitals from './reportWebVitals';

import 'focus-visible';
import 'styles/style.scss';

keycloak
  .init({
    onLoad: 'check-sso',
    checkLoginIframe: false
  })
  .then(() => {
    const root = createRoot(document.getElementById('root')!);
    root.render(
      <StrictMode>
        <App />
      </StrictMode>
    );
  });

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
// reportWebVitals();
