import { useEffect, useState, useCallback } from 'react';
import { toast } from 'sonner';
import { intersectionsApi } from '@/services/intersections';
import { recommendationsApi, type RecommendationResponse } from '@/services/recommendations';
import type { Intersection } from '@/types';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import { Lightbulb, RefreshCw, Loader2, CheckCircle2, XCircle, Pencil, Check, X } from 'lucide-react';
import { cn } from '@/lib/utils';

const WARRANTS = [
  {
    key: 'warrant_1',
    code: 'W1',
    title: 'Eight-Hour Vehicular Volume',
    desc: 'Volumes exceed thresholds for 8+ hours per day.',
  },
  {
    key: 'warrant_2',
    code: 'W2',
    title: 'Four-Hour Vehicular Volume',
    desc: 'Volumes exceed thresholds for 4+ hours per day.',
  },
  {
    key: 'warrant_4',
    code: 'W4',
    title: 'Pedestrian Volume',
    desc: 'Pedestrian crossing volume reaches specified threshold.',
  },
] as const;

type WarrantKey = 'warrant_1' | 'warrant_2' | 'warrant_4';

function WarrantPill({
  met,
  confidence,
  label,
}: {
  met: boolean;
  confidence: number;
  label: string;
}) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          {met ? (
            <CheckCircle2 className="size-3.5 text-emerald-600" />
          ) : (
            <XCircle className="size-3.5 text-muted-foreground" />
          )}
          <span className="text-xs font-medium">{label}</span>
        </div>
        <span className="text-[10px] text-muted-foreground">{Math.round(confidence * 100)}%</span>
      </div>
      <Progress
        value={confidence * 100}
        className={cn('h-1.5', met ? '[&>div]:bg-emerald-500' : '[&>div]:bg-muted-foreground/40')}
      />
    </div>
  );
}

function RecommendationCard({
  rec,
  onRegenerate,
  onNotesUpdate,
  regenerating,
}: {
  rec: RecommendationResponse;
  onRegenerate: () => void;
  onNotesUpdate: (id: number, notes: string | null) => Promise<void>;
  regenerating: boolean;
}) {
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesValue, setNotesValue] = useState(rec.notes ?? '');
  const [savingNotes, setSavingNotes] = useState(false);

  async function handleSaveNotes() {
    setSavingNotes(true);
    try {
      await onNotesUpdate(rec.id, notesValue.trim() || null);
      setEditingNotes(false);
    } finally {
      setSavingNotes(false);
    }
  }

  function handleCancelNotes() {
    setNotesValue(rec.notes ?? '');
    setEditingNotes(false);
  }

  return (
    <Card className={cn(
      'relative overflow-hidden',
      rec.recommended && 'ring-1 ring-emerald-500/40',
    )}>
      {rec.recommended && (
        <div className="absolute top-0 right-0 w-0 h-0"
          style={{
            borderTop: '40px solid',
            borderLeft: '40px solid transparent',
            borderTopColor: 'rgb(34 197 94 / 0.2)',
          }}
        />
      )}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="text-sm">{rec.intersection_name}</CardTitle>
            <CardDescription className="text-[10px] mt-0.5">
              Generated {new Date(rec.generated_at).toLocaleDateString('en-PH', {
                month: 'short', day: 'numeric', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
              })}
            </CardDescription>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <Badge
              variant="outline"
              className={cn(
                'text-[10px] font-semibold',
                rec.recommended
                  ? 'border-emerald-500/40 text-emerald-600 bg-emerald-50'
                  : 'border-muted text-muted-foreground',
              )}
            >
              {rec.recommended ? (
                <><Lightbulb className="size-2.5 mr-1" />Warranted</>
              ) : 'Not warranted'}
            </Badge>
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label="Re-run analysis"
              onClick={onRegenerate}
              disabled={regenerating}
            >
              {regenerating ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <RefreshCw className="size-3.5" aria-hidden="true" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>
      <Separator />
      <CardContent className="pt-3 flex flex-col gap-3">
        {WARRANTS.map(w => (
          <WarrantPill
            key={w.key}
            met={rec[`${w.key}_met` as `${WarrantKey}_met`]}
            confidence={rec[`${w.key}_confidence` as `${WarrantKey}_confidence`]}
            label={`${w.code} -${w.title}`}
          />
        ))}
        <div className="pt-1 border-t border-border">
          {editingNotes ? (
            <div className="flex flex-col gap-1.5">
              <Textarea
                value={notesValue}
                onChange={e => setNotesValue(e.target.value)}
                placeholder="Engineer notes…"
                className="text-[11px] min-h-[72px] resize-none"
                autoFocus
              />
              <div className="flex gap-1.5 justify-end">
                <Button size="icon" variant="ghost" className="size-6" aria-label="Cancel notes" onClick={handleCancelNotes} disabled={savingNotes}>
                  <X className="size-3" aria-hidden="true" />
                </Button>
                <Button size="icon" variant="ghost" className="size-6 text-emerald-600" aria-label="Save notes" onClick={handleSaveNotes} disabled={savingNotes}>
                  {savingNotes ? <Loader2 className="size-3 animate-spin" aria-hidden="true" /> : <Check className="size-3" aria-hidden="true" />}
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-start justify-between gap-1">
              <p className={cn('text-[11px] leading-relaxed flex-1', rec.notes ? 'text-muted-foreground' : 'text-muted-foreground/40 italic')}>
                {rec.notes ?? 'No notes'}
              </p>
              <Button size="icon" variant="ghost" className="size-5 shrink-0" aria-label="Edit notes" onClick={() => setEditingNotes(true)}>
                <Pencil className="size-2.5" aria-hidden="true" />
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function NoDataCard({ intersection, onGenerate, generating }: {
  intersection: Intersection;
  onGenerate: () => void;
  generating: boolean;
}) {
  return (
    <Card className="border-dashed">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm text-muted-foreground">{intersection.name}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground mb-3">No analysis yet.</p>
        <Button size="sm" variant="outline" onClick={onGenerate} disabled={generating}>
          {generating ? <Loader2 className="size-3.5 mr-1 animate-spin" /> : <Lightbulb className="size-3.5 mr-1" />}
          Run analysis
        </Button>
      </CardContent>
    </Card>
  );
}

export function RecommendationsPage() {
  const [intersections, setIntersections] = useState<Intersection[]>([]);
  const [recs, setRecs] = useState<RecommendationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingIds, setGeneratingIds] = useState<Set<number>>(new Set());

  async function load() {
    try {
      const [ints, r] = await Promise.all([
        intersectionsApi.list(),
        recommendationsApi.list(),
      ]);
      setIntersections(ints);
      setRecs(r);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleGenerate(intersectionId: number) {
    setGeneratingIds(prev => new Set(prev).add(intersectionId));
    try {
      const result = await recommendationsApi.generate(intersectionId);
      setRecs(prev => {
        const updated = prev.filter(r => r.intersection_id !== intersectionId);
        return [...updated, result];
      });
      toast.success('Analysis complete');
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setGeneratingIds(prev => {
        const s = new Set(prev);
        s.delete(intersectionId);
        return s;
      });
    }
  }

  const handleNotesUpdate = useCallback(async (id: number, notes: string | null) => {
    const result = await recommendationsApi.updateNotes(id, notes);
    setRecs(prev => prev.map(r => r.id === id ? result : r));
    toast.success('Notes saved');
  }, []);

  async function handleGenerateAll() {
    setGeneratingAll(true);
    try {
      const results = await recommendationsApi.generateAll();
      setRecs(results);
      const warranted = results.filter(r => r.recommended).length;
      toast.success(`Analysis complete -${warranted} intersection${warranted !== 1 ? 's' : ''} warranted`);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setGeneratingAll(false);
    }
  }

  const recByIntersection = new Map(recs.map(r => [r.intersection_id, r]));
  const warranted = recs.filter(r => r.recommended).length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Recommendations</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            MUTCD traffic signal warrant analysis -last 7 days of data
          </p>
        </div>
        <Button
          onClick={handleGenerateAll}
          disabled={generatingAll || loading || intersections.length === 0}
          size="sm"
        >
          {generatingAll
            ? <Loader2 className="size-3.5 mr-1.5 animate-spin" />
            : <RefreshCw className="size-3.5 mr-1.5" />
          }
          Run all
        </Button>
      </div>

      {/* Summary strip */}
      {!loading && recs.length > 0 && (
        <div className="flex gap-6 rounded-lg border border-border bg-card px-5 py-3 text-sm">
          <div className="flex items-center gap-1.5">
            <span className="text-lg font-bold tabular-nums text-emerald-600">{warranted}</span>
            <span className="text-muted-foreground">warranted</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-lg font-bold tabular-nums">{recs.length -warranted}</span>
            <span className="text-muted-foreground">not warranted</span>
          </div>
          <div className="flex items-center gap-1.5 ml-auto text-xs text-muted-foreground">
            {intersections.length -recs.length > 0 && (
              <span>{intersections.length -recs.length} intersections not yet analyzed</span>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-56" />)}
        </div>
      ) : intersections.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-20 text-muted-foreground">
          <Lightbulb className="size-10 opacity-30" />
          <p className="text-sm">No intersections configured</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {intersections.map(i => {
            const rec = recByIntersection.get(i.id);
            if (rec) {
              return (
                <RecommendationCard
                  key={i.id}
                  rec={rec}
                  onRegenerate={() => handleGenerate(i.id)}
                  onNotesUpdate={handleNotesUpdate}
                  regenerating={generatingIds.has(i.id)}
                />
              );
            }
            return (
              <NoDataCard
                key={i.id}
                intersection={i}
                onGenerate={() => handleGenerate(i.id)}
                generating={generatingIds.has(i.id)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
