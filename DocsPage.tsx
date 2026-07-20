import { useState } from "react";
import { BookOpen, Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function DocsPage() {
  const origin = window.location.origin;
  const [copied, setCopied] = useState<string | null>(null);

  const copy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(id);
    setTimeout(() => setCopied(null), 1500);
  };

  const curlSnippet = `curl ${origin}/v1/chat/completions \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "nexus-chat",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'`;

  const pythonSnippet = `from openai import OpenAI

client = OpenAI(
    api_key="sk-nx-YOUR_KEY",
    base_url="${origin}/v1",
)

# Streaming works with the official SDK, unmodified
stream = client.chat.completions.create(
    model="nexus-chat",
    messages=[{"role": "user", "content": "Write a haiku about APIs"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="")`;

  const codeSnippet = `# Code generation mode — the roadmap's tools=["code"] extension
curl ${origin}/v1/chat/completions \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "nexus-code",
    "tools": ["code"],
    "messages": [{"role": "user", "content": "Binary search in Python"}]
  }'`;

  const imageSnippet = `# Image generation — OpenAI-compatible endpoint
curl ${origin}/v1/images/generations \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"prompt": "a serene japanese garden at sunset"}'

# …or inline in chat (returns the image as markdown):
curl ${origin}/v1/chat/completions \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "enable_image": true,
    "messages": [{"role": "user", "content": "a cozy cabin in snow"}]
  }'`;

  const videoSnippet = `# Video generation inline in chat — returns the MP4 as markdown
curl ${origin}/v1/chat/completions \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "enable_video": true,
    "messages": [{"role": "user", "content": "waves on a beach at sunrise"}]
  }'

# Natural-language intent works too — no flag needed:
#   "generate a video of a rotating cube"

# Note: video rendering takes ~1–3 minutes (async upstream task).
# MP4 files are stored and served permanently from /media/*.mp4`;

  const sandboxSnippet = `# Code sandbox — the platform writes the code, runs it
# in an isolated sandbox (no network, CPU/memory/time limits),
# self-fixes on error, and returns code + real output.
curl ${origin}/v1/chat/completions \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "enable_code_execution": true,
    "messages": [{"role": "user", "content": "plot y=sin(x) and print the max value"}]
  }'

# The reply contains: generated code, sandbox output (stdout/stderr,
# exit code, duration), and /media URLs for any plots produced.
# Limits: 30s CPU, 512MB RAM, no network, python & javascript.`;

  const agentSnippet = `# Orchestration (Phase 3) — every request is routed by the
# central agent (TF-Agents policy when trained, rules otherwise).
# List available tools + active policy:
curl ${origin}/v1/agents \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY"

# Every chat response includes the routing decision:
curl ${origin}/v1/chat/completions \\
  -H "Authorization: Bearer sk-nx-YOUR_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"messages": [{"role": "user", "content": "draw a dragon"}]}'
# → "routing": {"action": "image_gen", "policy": "rules-v1",
#               "reason": "natural-language image intent detected"}

# Deploy your own TF-Agents policy: drop router_policy.json at
# TF_AGENT_POLICY_PATH and it takes over routing automatically.`;

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto px-8 py-10">
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2.5 mb-1.5">
          <BookOpen className="text-violet-500" size={24} /> Developer API
        </h1>
        <p className="text-sm text-muted-foreground mb-8">
          Drop-in OpenAI compatibility — point any OpenAI client at this gateway, no code changes needed.
        </p>

        <Card className="border-border/60 mb-6">
          <CardHeader>
            <CardTitle className="text-base">Base URL</CardTitle>
            <CardDescription>Replace <code>api.openai.com</code> with this gateway</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-sm bg-muted rounded-lg px-3 py-2.5 font-mono">{origin}/v1</code>
              <Button variant="outline" size="icon" onClick={() => copy("base", `${origin}/v1`)}>
                {copied === "base" ? <Check size={15} className="text-green-500" /> : <Copy size={15} />}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/60 mb-6">
          <CardHeader>
            <CardTitle className="text-base">Quickstart</CardTitle>
            <CardDescription>Authenticate with a key from the API Keys page</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="python">
              <TabsList className="mb-4">
                <TabsTrigger value="python">Python SDK</TabsTrigger>
                <TabsTrigger value="curl">cURL</TabsTrigger>
                <TabsTrigger value="code">Code mode</TabsTrigger>
                <TabsTrigger value="image">Images</TabsTrigger>
                <TabsTrigger value="video">Video</TabsTrigger>
                <TabsTrigger value="sandbox">Sandbox</TabsTrigger>
                <TabsTrigger value="agent">Agents</TabsTrigger>
              </TabsList>
              {(
                [
                  ["python", pythonSnippet],
                  ["curl", curlSnippet],
                  ["code", codeSnippet],
                  ["image", imageSnippet],
                  ["video", videoSnippet],
                  ["sandbox", sandboxSnippet],
                  ["agent", agentSnippet],
                ] as const
              ).map(([id, snippet]) => (
                <TabsContent key={id} value={id} className="relative">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute top-2 right-2 h-8 w-8 text-muted-foreground"
                    onClick={() => copy(id, snippet)}
                  >
                    {copied === id ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                  </Button>
                  <pre className="text-xs leading-relaxed bg-zinc-950 text-zinc-100 dark:bg-black/60 rounded-xl p-4 overflow-x-auto">
                    {snippet}
                  </pre>
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>

        <Card className="border-border/60">
          <CardHeader>
            <CardTitle className="text-base">Models</CardTitle>
            <CardDescription>Available via <code>GET /v1/models</code></CardDescription>
          </CardHeader>
          <CardContent className="space-y-2.5 text-sm">
            {[
              ["nexus-chat", "General chat — routed to GLM-4-Flash (default)"],
              ["nexus-code", 'Code generation — pair with tools=["code"] for best results'],
              ["glm-4-flash / glm-4-air / glm-4-plus", "Direct GLM model passthrough"],
            ].map(([name, desc]) => (
              <div key={name} className="flex items-baseline gap-3 flex-wrap">
                <code className="text-xs bg-muted rounded px-2 py-1 font-mono shrink-0">{name}</code>
                <span className="text-muted-foreground">{desc}</span>
              </div>
            ))}
            <div className="pt-3 text-xs text-muted-foreground border-t border-border/60 mt-4">
              Interactive OpenAPI reference (auto-generated by FastAPI):{" "}
              <a className="text-violet-500 hover:underline" href="/docs" target="_blank" rel="noreferrer">/docs</a>
              {" · "}
              <a className="text-violet-500 hover:underline" href="/redoc" target="_blank" rel="noreferrer">/redoc</a>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
