import { useEffect, useState, useRef } from 'react';
import { useOutletContext, Link } from 'react-router-dom';
import { intersectionsApi } from '@/services/intersections';
import { aggregationApi } from '@/services/aggregation';
import type { Intersection, AggregationRow } from '@/types';
import type { SSEStatus } from '@/hooks/useSSE';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { MapPin, RefreshCw } from 'lucide-react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

const PEDESTRIAN_TYPES = new Set(['pedestrian', 'person']);

interface OutletCtx {
  sseData: AggregationRow[] | null;
  sseStatus: SSEStatus;
}

function densityColor(count: number): string {
  if (count === 0)       return '#6b7280'; // gray
  if (count < 50)        return '#22c55e'; // green
  if (count < 150)       return '#f59e0b'; // amber
  if (count < 400)       return '#f97316'; // orange
  return                        '#ef4444'; // red
}

function densityLabel(count: number): string {
  if (count === 0)    return 'No data';
  if (count < 50)     return 'Low';
  if (count < 150)    return 'Moderate';
  if (count < 400)    return 'High';
  return                     'Very High';
}

interface IntersectionData {
  intersection: Intersection;
  vehicles: number;
  pedestrians: number;
  total: number;
}

// Recenter map if intersections have coords
function MapController({ center }: { center: [number, number] }) {
  const map = useMap();
  const initialized = useRef(false);
  useEffect(() => {
    if (!initialized.current && center[0] !== 0) {
      map.setView(center, 14);
      initialized.current = true;
    }
  }, [center, map]);
  return null;
}

export function HeatmapPage() {
  const { sseData } = useOutletContext<OutletCtx>();
  const [intersections, setIntersections] = useState<Intersection[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [historyData, setHistoryData] = useState<AggregationRow[]>([]);

  // Tagum City center as fallback
  const DEFAULT_CENTER: [number, number] = [7.4478, 125.8075];

  async function loadData() {
    try {
      const ints = await intersectionsApi.list();
      setIntersections(ints);

      // Load last 1 hour of history as baseline when SSE has no data yet
      const now = new Date();
      const oneHourAgo = new Date(now.getTime() -60 * 60 * 1000);
      const hist = await aggregationApi.history({
        start: oneHourAgo.toISOString(),
        end: now.toISOString(),
        bucket: 'hour',
      });
      setHistoryData(hist);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 30_000);
    return () => clearInterval(timer);
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    await loadData();
  }

  // Prefer live SSE data; fall back to last-hour history
  const source = (sseData && sseData.length > 0) ? sseData : historyData;

  // Aggregate counts per intersection
  const byIntersection = new Map<number, { vehicles: number; pedestrians: number }>();
  for (const row of source) {
    const entry = byIntersection.get(row.intersection_id) ?? { vehicles: 0, pedestrians: 0 };
    if (PEDESTRIAN_TYPES.has(row.object_type)) {
      entry.pedestrians += row.count;
    } else {
      entry.vehicles += row.count;
    }
    byIntersection.set(row.intersection_id, entry);
  }

  const items: IntersectionData[] = intersections.map(i => {
    const counts = byIntersection.get(i.id) ?? { vehicles: 0, pedestrians: 0 };
    return { intersection: i, ...counts, total: counts.vehicles + counts.pedestrians };
  });

  // Center map on first intersection with valid coords
  const withCoords = intersections.filter(i => i.latitude && i.longitude);
  const mapCenter: [number, number] = withCoords.length > 0
    ? [withCoords[0].latitude, withCoords[0].longitude]
    : DEFAULT_CENTER;

  const mappable = items.filter(d => d.intersection.latitude && d.intersection.longitude);
  const maxTotal = Math.max(1, ...items.map(d => d.total));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Traffic Heatmap</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Live density by intersection -{sseData && sseData.length > 0 ? 'live SSE' : 'last hour'}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={refreshing}>
          <RefreshCw className={`size-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 rounded-lg border border-border bg-card px-5 py-2.5 text-xs">
        <span className="text-muted-foreground font-medium">Density:</span>
        {[
          { label: 'No data', color: '#6b7280' },
          { label: 'Low',     color: '#22c55e' },
          { label: 'Moderate', color: '#f59e0b' },
          { label: 'High',    color: '#f97316' },
          { label: 'Very High', color: '#ef4444' },
        ].map(({ label, color }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className="size-3 rounded-full" style={{ backgroundColor: color }} />
            <span className="text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>

      {/* Map */}
      {loading ? (
        <Skeleton className="h-[500px] w-full rounded-lg" />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border" style={{ height: 500, isolation: 'isolate' }}>
          <MapContainer
            center={mapCenter}
            zoom={14}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom
          >
            <MapController center={mapCenter} />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {mappable.length === 0 && (
              <CircleMarker
                center={DEFAULT_CENTER}
                radius={12}
                pathOptions={{ color: '#6b7280', fillColor: '#6b7280', fillOpacity: 0.6 }}
              >
                <Popup>
                  <div className="text-xs">
                    <p className="font-semibold">No intersections with coordinates</p>
                    <p className="text-gray-500">Add lat/lng to intersections to pin them here.</p>
                  </div>
                </Popup>
              </CircleMarker>
            )}

            {mappable.map(({ intersection, vehicles, pedestrians, total }) => {
              const color = densityColor(total);
              // Scale radius 12–40 relative to max
              const radius = 12 + Math.round(28 * (total / maxTotal));
              return (
                <CircleMarker
                  key={intersection.id}
                  center={[intersection.latitude, intersection.longitude]}
                  radius={radius}
                  pathOptions={{
                    color,
                    fillColor: color,
                    fillOpacity: 0.55,
                    weight: 2,
                  }}
                >
                  <Popup>
                    <div className="text-xs min-w-[160px]">
                      <p className="font-semibold text-sm mb-1">{intersection.name}</p>
                      <div className="flex flex-col gap-0.5">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Density</span>
                          <span className="font-medium" style={{ color }}>{densityLabel(total)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Vehicles</span>
                          <span className="font-medium">{vehicles}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Pedestrians</span>
                          <span className="font-medium">{pedestrians}</span>
                        </div>
                        <div className="flex justify-between border-t border-gray-200 pt-0.5 mt-0.5">
                          <span className="text-gray-500">Total</span>
                          <span className="font-semibold">{total}</span>
                        </div>
                      </div>
                      <div className="flex gap-2 pt-1.5 border-t border-gray-200 mt-1">
                        <Link
                          to={`/reports?intersection_id=${intersection.id}`}
                          className="text-[10px] text-blue-600 hover:underline"
                        >
                          View reports →
                        </Link>
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>
      )}

      {/* Intersection list */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map(({ intersection, vehicles, pedestrians, total }) => {
          const color = densityColor(total);
          return (
            <div
              key={intersection.id}
              className="rounded-lg border border-border bg-card p-4 flex items-start gap-3"
            >
              <div
                className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full"
                style={{ backgroundColor: color + '22', color }}
              >
                <MapPin className="size-4" aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{intersection.name}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {vehicles} vehicles · {pedestrians} pedestrians
                </p>
              </div>
              <Badge
                variant="outline"
                className="shrink-0 text-[10px] font-semibold"
                style={{ borderColor: color + '80', color, backgroundColor: color + '15' }}
              >
                {densityLabel(total)}
              </Badge>
            </div>
          );
        })}
        {!loading && items.length === 0 && (
          <div className="col-span-full flex flex-col items-center gap-3 py-16 text-muted-foreground">
            <MapPin className="size-10 opacity-30" />
            <p className="text-sm">No intersections configured</p>
          </div>
        )}
      </div>
    </div>
  );
}
