import { Navigate, Route, Routes } from "react-router-dom";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { AppDataProvider } from "./context/AppData";
import { SearchProvider } from "./context/SearchContext";
import { ClusterAnalysisPage } from "./pages/ClusterAnalysisPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DataImportPage } from "./pages/DataImportPage";
import { ExportPage } from "./pages/ExportPage";
import { FindNearestHubPage } from "./pages/FindNearestHubPage";
import { HubDirectoryPage } from "./pages/HubDirectoryPage";
import { LiveMapPage } from "./pages/LiveMapPage";
import { RouteHistoryPage } from "./pages/RouteHistoryPage";
import { SettingsPage } from "./pages/SettingsPage";

export default function App() {
  return (
    <AppDataProvider>
      <SearchProvider>
        <Routes>
          <Route element={<DashboardLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="map" element={<LiveMapPage />} />
            <Route path="find" element={<FindNearestHubPage />} />
            <Route path="clusters" element={<ClusterAnalysisPage />} />
            <Route path="hubs" element={<HubDirectoryPage />} />
            <Route path="history" element={<RouteHistoryPage />} />
            <Route path="import" element={<DataImportPage />} />
            <Route path="export" element={<ExportPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </SearchProvider>
    </AppDataProvider>
  );
}
