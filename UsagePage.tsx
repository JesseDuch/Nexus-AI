import { useEffect, useState } from "react";
import { BarChart3, Coins, ArrowDownUp, Activity, Image as ImageIcon, Clapperboard, SquareTerminal } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type UsageSummary } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

export default function UsagePage() {
  const [usage, setUsage] = useState<UsageSummary | null>(null);

  useEffect(() => {
    api.usage().then(setUsage).catch(() => {});
  }, []);

  const stats = [
    { label: "Total tokens", value: usage ? fmt(usage.total_tokens) : "—", icon: Coins },
    { label: "Prompt tokens", value: usage ? fmt(usage.prompt_tokens) : "—", icon: ArrowDownUp },
    { label: "Completion tokens", value: usage ? fmt(usage.completion_tokens) : "—", icon: ArrowDownUp },
    { label: "Images generated", value: usage ? fmt(usage.image_count) : "—", icon: ImageIcon },
    { label: "Videos generated", value: usage ? fmt(usage.video_count) : "—", icon: Clapperboard },
    { label: "Code executions", value: usage ? fmt(usage.code_exec_count) : "—", icon: SquareTerminal },
    { label: "API requests", value: usage ? fmt(usage.request_count) : "—", icon: Activity },
  ];

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto px-8 py-10">
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2.5 mb-1.5">
          <BarChart3 className="text-violet-500" size={24} /> Usage
        </h1>
        <p className="text-sm text-muted-foreground mb-8">
          Token consumption across web console and API-key calls. Quotas and per-key limits arrive in Phase 7.
        </p>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-7 gap-4 mb-6">
          {stats.map((s) => (
            <Card key={s.label} className="border-border/60">
              <CardContent className="pt-5 pb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">{s.label}</span>
                  <s.icon size={14} className="text-violet-500" />
                </div>
                <div className="text-2xl font-semibold tracking-tight">{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {usage && Object.keys(usage.routing || {}).length > 0 && (
          <Card className="border-border/60 mb-6">
            <CardHeader>
              <CardTitle className="text-base">Orchestration routing</CardTitle>
              <CardDescription>How the agent routed your requests (Phase 3)</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2.5">
              {Object.entries(usage.routing).map(([action, count]) => (
                <div key={action} className="flex items-center gap-2 rounded-full border border-border px-3.5 py-1.5 text-sm">
                  <span className="text-violet-500 font-medium">{action}</span>
                  <span className="text-muted-foreground">{count}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Last 14 days</CardTitle>
            <CardDescription>Total tokens per day</CardDescription>
          </CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={usage?.daily || []} margin={{ left: -18, right: 8, top: 4 }}>
                <defs>
                  <linearGradient id="tok" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} stroke="hsl(var(--muted-foreground))" tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Area type="monotone" dataKey="tokens" stroke="#8b5cf6" strokeWidth={2} fill="url(#tok)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
