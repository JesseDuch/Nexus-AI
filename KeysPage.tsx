import { useEffect, useState } from "react";
import { Copy, Check, KeyRound, Loader2, Plus, RefreshCw, Trash2, Eye, EyeOff } from "lucide-react";
import { api, type ApiKey } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function KeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [open, setOpen] = useState(false);
  const [freshKey, setFreshKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showKey, setShowKey] = useState(false);

  const load = () => {
    setLoading(true);
    api.listKeys().then(setKeys).finally(() => setLoading(false));
  };
  useEffect(load, []);

  const create = async () => {
    setCreating(true);
    try {
      const k = await api.createKey(newName || "Default key");
      setFreshKey(k.key!);
      setNewName("");
      load();
    } finally {
      setCreating(false);
    }
  };

  const reset = async (id: number) => {
    const k = await api.resetKey(id);
    setFreshKey(k.key!);
    load();
  };

  const revoke = async (id: number) => {
    await api.revokeKey(id);
    load();
  };

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto px-8 py-10">
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2.5">
              <KeyRound className="text-violet-500" size={24} /> API Keys
            </h1>
            <p className="text-sm text-muted-foreground mt-1.5">
              Keys authenticate calls to <code className="text-xs bg-muted px-1.5 py-0.5 rounded">/v1/chat/completions</code>.
              Use them with any OpenAI SDK — just swap the base URL.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white">
                <Plus size={16} className="mr-1.5" /> New key
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create API key</DialogTitle>
                <DialogDescription>
                  The full key is shown exactly once. Store it somewhere safe.
                </DialogDescription>
              </DialogHeader>
              <Input
                placeholder="Key name, e.g. production-backend"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <DialogFooter>
                <Button onClick={create} disabled={creating}>
                  {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Create
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        {freshKey && (
          <Card className="mb-6 border-violet-500/40 bg-violet-500/5">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Your new key — copy it now</CardTitle>
              <CardDescription>It will not be shown again.</CardDescription>
            </CardHeader>
            <CardContent className="flex items-center gap-2">
              <code className="flex-1 text-sm bg-background border border-border rounded-lg px-3 py-2.5 font-mono truncate">
                {showKey ? freshKey : freshKey.slice(0, 10) + "•".repeat(24)}
              </code>
              <Button variant="outline" size="icon" onClick={() => setShowKey(!showKey)}>
                {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
              </Button>
              <Button variant="outline" size="icon" onClick={() => copy(freshKey)}>
                {copied ? <Check size={15} className="text-green-500" /> : <Copy size={15} />}
              </Button>
              <Button variant="ghost" onClick={() => setFreshKey(null)}>Dismiss</Button>
            </CardContent>
          </Card>
        )}

        <Card className="border-border/60">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Key</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last used</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((k) => (
                  <TableRow key={k.id}>
                    <TableCell className="font-medium">{k.name}</TableCell>
                    <TableCell>
                      <code className="text-xs text-muted-foreground">{k.prefix}…</code>
                    </TableCell>
                    <TableCell>
                      {k.revoked ? (
                        <Badge variant="destructive">Revoked</Badge>
                      ) : (
                        <Badge className="bg-green-500/10 text-green-600 dark:text-green-400 hover:bg-green-500/20">Active</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "Never"}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(k.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="icon" title="Reset key" onClick={() => reset(k.id)}>
                          <RefreshCw size={15} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Revoke key"
                          disabled={k.revoked}
                          onClick={() => revoke(k.id)}
                          className="hover:text-destructive"
                        >
                          <Trash2 size={15} />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && keys.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-10 text-muted-foreground">
                      No keys yet — create one to call the API from your app.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
