import { useEffect, useState } from "react";
import { Shield, Users, KeyRound, ScrollText } from "lucide-react";
import { api, type AdminStats, type AdminUser, type AdminKey, type AuditRow } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

function fmt(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

export default function AdminPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [keys, setKeys] = useState<AdminKey[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.adminStats(), api.adminUsers(), api.adminKeys(), api.adminAudit()])
      .then(([s, u, k, a]) => {
        setStats(s);
        setUsers(u);
        setKeys(k);
        setAudit(a);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load admin data"));
  }, []);

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2"><Shield className="text-destructive" /> Access denied</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const statCards = stats
    ? [
        ["Users", stats.users],
        ["API keys", stats.api_keys],
        ["Total requests", stats.requests_total],
        ["Total tokens", stats.tokens_total],
        ["Media assets", stats.media_total],
        ["Routing decisions", stats.routing_logs],
        ["Audit entries", stats.audit_logs],
      ]
    : [];

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-5xl mx-auto px-8 py-10">
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2.5 mb-1.5">
          <Shield className="text-violet-500" size={24} /> Admin panel
        </h1>
        <p className="text-sm text-muted-foreground mb-8">Platform-wide usage, users, keys and the audit trail.</p>

        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-8">
          {statCards.map(([label, value]) => (
            <Card key={label as string} className="border-border/60">
              <CardContent className="pt-5 pb-4">
                <div className="text-xs text-muted-foreground mb-1.5">{label}</div>
                <div className="text-xl font-semibold tracking-tight">{fmt(value as number)}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Tabs defaultValue="users">
          <TabsList className="mb-4">
            <TabsTrigger value="users"><Users size={14} className="mr-1.5" />Users</TabsTrigger>
            <TabsTrigger value="keys"><KeyRound size={14} className="mr-1.5" />Keys</TabsTrigger>
            <TabsTrigger value="audit"><ScrollText size={14} className="mr-1.5" />Audit log</TabsTrigger>
          </TabsList>

          <TabsContent value="users">
            <Card className="border-border/60"><CardContent className="p-0">
              <Table>
                <TableHeader><TableRow>
                  <TableHead>Email</TableHead><TableHead>Name</TableHead><TableHead>Role</TableHead>
                  <TableHead>Keys</TableHead><TableHead>Tokens</TableHead><TableHead>Joined</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell className="font-medium">{u.email}</TableCell>
                      <TableCell>{u.name}</TableCell>
                      <TableCell>{u.is_admin ? <Badge className="bg-violet-500/10 text-violet-600 dark:text-violet-300">Admin</Badge> : <Badge variant="secondary">User</Badge>}</TableCell>
                      <TableCell>{u.api_keys}</TableCell>
                      <TableCell>{fmt(u.tokens)}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">{new Date(u.created_at).toLocaleDateString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent></Card>
          </TabsContent>

          <TabsContent value="keys">
            <Card className="border-border/60"><CardContent className="p-0">
              <Table>
                <TableHeader><TableRow>
                  <TableHead>Owner</TableHead><TableHead>Name</TableHead><TableHead>Key</TableHead>
                  <TableHead>Status</TableHead><TableHead>Last used</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {keys.map((k) => (
                    <TableRow key={k.id}>
                      <TableCell className="font-medium">{k.owner}</TableCell>
                      <TableCell>{k.name}</TableCell>
                      <TableCell><code className="text-xs text-muted-foreground">{k.prefix}…</code></TableCell>
                      <TableCell>{k.revoked ? <Badge variant="destructive">Revoked</Badge> : <Badge className="bg-green-500/10 text-green-600 dark:text-green-400">Active</Badge>}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">{k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "Never"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent></Card>
          </TabsContent>

          <TabsContent value="audit">
            <Card className="border-border/60"><CardContent className="p-0">
              <Table>
                <TableHeader><TableRow>
                  <TableHead>Time</TableHead><TableHead>Method</TableHead><TableHead>Path</TableHead>
                  <TableHead>Status</TableHead><TableHead>Latency</TableHead><TableHead>Request ID</TableHead>
                </TableRow></TableHeader>
                <TableBody>
                  {audit.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="text-muted-foreground text-sm whitespace-nowrap">{new Date(r.created_at).toLocaleTimeString()}</TableCell>
                      <TableCell><code className="text-xs">{r.method}</code></TableCell>
                      <TableCell className="max-w-[260px] truncate"><code className="text-xs">{r.path}</code></TableCell>
                      <TableCell>
                        <Badge variant="secondary" className={r.status_code >= 400 ? "bg-red-500/10 text-red-600 dark:text-red-400" : "bg-green-500/10 text-green-600 dark:text-green-400"}>
                          {r.status_code}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">{r.latency_ms}ms</TableCell>
                      <TableCell><code className="text-[10px] text-muted-foreground">{r.request_id}</code></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent></Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
