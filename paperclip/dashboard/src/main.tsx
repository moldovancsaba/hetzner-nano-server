import React from 'react';
import { createRoot } from 'react-dom/client';
import { GdsProvider } from '@sovereignsquad/gds/client';
import '@sovereignsquad/gds-theme/styles.css';
import { Dashboard } from './Dashboard';
createRoot(document.getElementById('root')!).render(<React.StrictMode><GdsProvider><Dashboard /></GdsProvider></React.StrictMode>);
