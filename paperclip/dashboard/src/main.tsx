import React from 'react';
import { createRoot } from 'react-dom/client';
import { GdsProvider } from '@sovereignsquad/gds/client';
import '@sovereignsquad/gds-theme/styles.css';
import { Dashboard } from './Dashboard';
import { CompanyDashboard } from './CompanyDashboard';
const View = ['/factory', '/factory/'].includes(window.location.pathname) ? CompanyDashboard : Dashboard;
createRoot(document.getElementById('root')!).render(<React.StrictMode><GdsProvider><View /></GdsProvider></React.StrictMode>);
