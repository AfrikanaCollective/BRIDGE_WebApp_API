// frontend/src/index.js

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import App from './App';
import store from './store/store';
import './design-system/tokens.css';
import '@picocss/pico/css/pico.min.css';
import './styles/index.css';
import './styles/base.css';
import './styles/components.css';
import './styles/typography.css';
import 'react-toastify/dist/ReactToastify.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
const basename = process.env.PUBLIC_URL;

root.render(
    <React.StrictMode>
        <Provider store={store}>
            <BrowserRouter basename={basename}>
                <App />
            </BrowserRouter>
        </Provider>
    </React.StrictMode>
);
