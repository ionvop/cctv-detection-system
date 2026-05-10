import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { intersectionsApi } from '@/services/intersections';
import { streetsApi } from '@/services/streets';
import { cctvsApi } from '@/services/cctvs';
import { request } from '@/services/api';
import type { Region } from '@/types';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import {
  CheckCircle2, Circle, ChevronDown, ChevronUp,
  MapPin, Camera, Layers, BarChart3, GitBranch,
  ArrowRight, X, Rocket,
} from 'lucide-react';

const DISMISS_KEY = 'eyegila_setup_v1';

interface SetupData {
  intersections: number;
  streets: number;
  cctvs: number;
  regions: number;
}

const STEPS = [
  {
    id: 'intersection',
    title: 'Create an intersection',
    subtitle: 'Define a location and pin it on the map',
    detail:
      'Go to Intersections and click "Add Intersection". Name it after the real location (e.g. "City Hall Junction") and pin its GPS coordinates by clicking the map or entering them manually.',
    href: '/intersections',
    action: 'Open Intersections',
    Icon: MapPin,
    done: (d: SetupData) => d.intersections > 0,
    blocked: (_d: SetupData) => false,
  },
  {
    id: 'streets',
    title: 'Add approach streets',
    subtitle: 'Name each traffic direction entering the intersection',
    detail:
      'Expand an intersection row and click "+ Street". Add one entry per approach (e.g. "Northbound", "Rizal Ave"). Streets become the detection zones you draw on the camera frame.',
    href: '/intersections',
    action: 'Open Intersections',
    Icon: GitBranch,
    done: (d: SetupData) => d.streets > 0,
    blocked: (d: SetupData) => d.intersections === 0,
  },
  {
    id: 'camera',
    title: 'Add a CCTV camera',
    subtitle: 'Connect a camera via its RTSP stream URL',
    detail:
      'Go to Cameras and click "Add Camera". Enter the RTSP stream URL (e.g. rtsp://192.168.1.10:554/ch01), select the intersection it covers, and save. A detection worker will automatically claim and start processing the stream.',
    href: '/cameras',
    action: 'Open Cameras',
    Icon: Camera,
    done: (d: SetupData) => d.cctvs > 0,
    blocked: (d: SetupData) => d.intersections === 0,
  },
  {
    id: 'regions',
    title: 'Draw detection regions',
    subtitle: 'Mark polygon zones on the video for each approach street',
    detail:
      'Open a camera and scroll to the Region Editor. Click "New Region", choose a street approach and direction (inbound or outbound), then click on the live video to place vertices. Click the first vertex again to close the polygon. The system counts detections inside each region.',
    href: '/cameras',
    action: 'Open Cameras',
    Icon: Layers,
    done: (d: SetupData) => d.regions > 0,
    blocked: (d: SetupData) => d.cctvs === 0 || d.streets === 0,
  },
  {
    id: 'monitor',
    title: 'Start monitoring traffic',
    subtitle: 'View live counts, reports, and warrant recommendations',
    detail:
      'The Dashboard shows real-time vehicle and pedestrian counts as workers process frames. Use Reports to view hourly and daily trends. Visit Recommendations to run MUTCD warrant analysis and determine if a traffic signal is needed at an intersection.',
    href: '/',
    action: 'View Dashboard',
    Icon: BarChart3,
    done: (d: SetupData) => d.regions > 0,
    blocked: (d: SetupData) => d.regions === 0,
  },
] as const;

export function SetupGuide() {
  const [data, setData] = useState<SetupData | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(
    () => localStorage.getItem(DISMISS_KEY) === '1',
  );

  useEffect(() => {
    if (dismissed) return;
    Promise.allSettled([
      intersectionsApi.list(),
      streetsApi.list(),
      cctvsApi.list(),
      request<Region[]>('/regions/'),
    ]).then(([ints, strs, cams, regs]) => {
      const d: SetupData = {
        intersections: ints.status === 'fulfilled' ? ints.value.length : 0,
        streets:       strs.status === 'fulfilled' ? strs.value.length : 0,
        cctvs:         cams.status === 'fulfilled' ? cams.value.length : 0,
        regions:       regs.status === 'fulfilled' ? regs.value.length : 0,
      };
      setData(d);
      const first = STEPS.find(s => !s.done(d) && !s.blocked(d));
      if (first) setExpanded(first.id);
    });
  }, [dismissed]);

  function dismiss() {
    localStorage.setItem(DISMISS_KEY, '1');
    setDismissed(true);
  }

  if (dismissed || !data) return null;

  const completedCount = STEPS.filter(s => s.done(data)).length;
  const allDone = completedCount === STEPS.length;
  const progress = Math.round((completedCount / STEPS.length) * 100);

  return (
    <Card className="overflow-hidden border-border">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 px-5 py-4 border-b border-border">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex-shrink-0 flex items-center justify-center size-8 rounded-lg bg-primary/10 text-primary">
            <Rocket className="size-4" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-sm">
              {allDone ? 'Setup complete' : 'Get started with EyeGila'}
            </p>
            <p className="text-xs text-muted-foreground">
              {allDone
                ? 'All steps done. Your system is monitoring traffic.'
                : `${completedCount} of ${STEPS.length} steps completed`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="w-24 hidden sm:block">
            <Progress value={progress} className="h-1.5" />
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-7 text-muted-foreground hover:text-foreground"
            onClick={dismiss}
            aria-label="Dismiss setup guide"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      </div>

      {/* Steps */}
      <div className="divide-y divide-border">
        {STEPS.map(step => {
          const done    = step.done(data);
          const blocked = step.blocked(data);
          const open    = expanded === step.id;

          return (
            <div key={step.id} className={cn(blocked && 'opacity-40 pointer-events-none')}>
              <button
                type="button"
                className="w-full flex items-center gap-3.5 px-5 py-3.5 hover:bg-muted/40 transition-colors text-left"
                onClick={() => setExpanded(open ? null : step.id)}
                aria-expanded={open}
              >
                <span className="flex-shrink-0">
                  {done
                    ? <CheckCircle2 className="size-5 text-emerald-500" />
                    : <Circle className="size-5 text-muted-foreground/40" />}
                </span>

                <span className={cn(
                  'flex-shrink-0 flex items-center justify-center size-7 rounded-md',
                  done
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
                    : 'bg-primary/10 text-primary',
                )}>
                  <step.Icon className="size-3.5" />
                </span>

                <div className="flex-1 min-w-0">
                  <p className={cn(
                    'text-sm font-medium leading-none mb-0.5',
                    done && 'text-muted-foreground line-through',
                  )}>
                    {step.title}
                  </p>
                  <p className="text-xs text-muted-foreground truncate">{step.subtitle}</p>
                </div>

                <span className="flex-shrink-0 text-muted-foreground">
                  {open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
                </span>
              </button>

              {open && (
                <div className="px-5 pb-4 pl-[72px]">
                  <p className="text-sm text-muted-foreground leading-relaxed mb-3">
                    {step.detail}
                  </p>
                  {!done && (
                    <Button size="sm" asChild>
                      <Link to={step.href}>
                        {step.action}
                        <ArrowRight className="size-3.5 ml-1.5" />
                      </Link>
                    </Button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
