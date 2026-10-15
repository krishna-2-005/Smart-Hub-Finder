import { GoogleEarthGuide, KMLExportPanel } from "../components/KMLExportPanel";
import { PageHeader } from "../components/ui";

export function ExportPage() {
  return (
    <div className="mx-auto max-w-[1400px] space-y-5 p-4 sm:p-6">
      <PageHeader
        title="Export to Google Earth"
        description="Generate Google Earth–compatible KML for clusters, hubs and road routes, plus CSV and GeoJSON reports."
      />
      <div className="grid gap-5 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <KMLExportPanel />
        </div>
        <div className="xl:col-span-2">
          <GoogleEarthGuide />
        </div>
      </div>
    </div>
  );
}
