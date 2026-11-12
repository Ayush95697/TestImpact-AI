import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import { MainLayout } from './layouts/MainLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { ChangeRequestsPage } from './pages/ChangeRequestsPage';
import { ImpactAnalysisPage } from './pages/ImpactAnalysisPage';
import { AnalysisHistoryPage } from './pages/AnalysisHistoryPage';
import { AboutPage } from './pages/AboutPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <BrowserRouter>
            <MainLayout>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/projects" element={<ProjectsPage />} />
                <Route path="/change-requests" element={<ChangeRequestsPage />} />
                <Route path="/impact-analysis" element={<ImpactAnalysisPage />} />
                <Route path="/impact-analysis/:runId" element={<ImpactAnalysisPage />} />
                <Route path="/analysis-history" element={<AnalysisHistoryPage />} />
                <Route path="/about" element={<AboutPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </MainLayout>
          </BrowserRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
};

export default App;

