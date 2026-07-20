import { useCallback, useEffect, useRef, useState } from "react";
import {
  Loader2, Plus, Send, Trash2, MessageSquare, Code2, Bot, User as UserIcon,
  ImagePlus, Images, X, Clapperboard, SquareTerminal, Route, ThumbsUp, ThumbsDown,
} from "lucide-react";
import { api, streamConsoleChat, type ChatMessage, type Conversation, type MediaAsset, type RoutingInfo } from "@/lib/api";
import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

const SUGGESTIONS = [
  "Compute the first 10 Fibonacci numbers and run the code",
  "Draw a serene Japanese garden at sunset",
  "Generate a video of waves on a beach at sunrise",
  "Plot y=sin(x) and run it in the sandbox",
];

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState<"nexus-chat" | "nexus-code">("nexus-chat");
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [forceImage, setForceImage] = useState(false);
  const [forceVideo, setForceVideo] = useState(false);
  const [forceCode, setForceCode] = useState(false);
  const [mediaOpen, setMediaOpen] = useState(false);
  const [media, setMedia] = useState<MediaAsset[]>([]);
  const [routing, setRouting] = useState<RoutingInfo | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<number, number>>({});
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const refreshConversations = useCallback(() => {
    api.listConversations().then(setConversations).catch(() => {});
  }, []);

  const refreshMedia = useCallback(() => {
    api.listMedia().then(setMedia).catch(() => {});
  }, []);

  useEffect(() => {
    refreshMedia();
  }, [refreshMedia]);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamText]);

  const openConversation = async (id: number) => {
    if (streaming) return;
    setActiveId(id);
    try {
      const detail = await api.getConversation(id);
      setMessages(detail.messages.map((m) => ({ role: m.role, content: m.content })));
    } catch {
      setMessages([]);
    }
  };

  const newChat = () => {
    if (streaming) return;
    setActiveId(null);
    setMessages([]);
  };

  const removeConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await api.deleteConversation(id).catch(() => {});
    if (activeId === id) newChat();
    refreshConversations();
  };

  const send = async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || streaming) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: message }]);
    setStreaming(true);
    setStreamText("");
    setStatus(null);
    setRouting(null);
    const wantImage = forceImage;
    const wantVideo = forceVideo;
    const wantCode = forceCode;
    setForceImage(false);
    setForceVideo(false);
    setForceCode(false);

    const controller = new AbortController();
    abortRef.current = controller;
    let acc = "";

    try {
      await streamConsoleChat(
        {
          conversation_id: activeId,
          message,
          model,
          enable_image: wantImage || undefined,
          enable_video: wantVideo || undefined,
          enable_code_execution: wantCode || undefined,
        },
        {
          onMeta: (id) => {
            setActiveId(id);
            refreshConversations();
          },
          onRouting: (r) => setRouting(r),
          onStatus: (s) => {
            if (s === "generating_image") setStatus("Painting your image…");
            else if (s === "generating_video") setStatus("Rendering your video… (1–3 min)");
            else if (s === "writing_code") setStatus("Writing code, then running it in the sandbox…");
            else setStatus(s);
          },
          onToken: (t) => {
            setStatus(null);
            acc += t;
            setStreamText(acc);
          },
          onError: (msg) => {
            acc = acc || `⚠️ ${msg}`;
            setStreamText(acc);
          },
        },
        controller.signal,
      );
    } catch (e) {
      acc = acc || `⚠️ ${e instanceof Error ? e.message : "Request failed"}`;
    } finally {
      setStreaming(false);
      setStreamText("");
      setStatus(null);
      if (acc) setMessages((m) => [...m, { role: "assistant", content: acc }]);
      refreshConversations();
      refreshMedia();
    }
  };

  return (
    <div className="flex h-full min-h-0">
      {/* Conversation list */}
      <div className="w-64 shrink-0 border-r border-border/60 flex flex-col bg-card/30">
        <div className="p-3">
          <Button
            onClick={newChat}
            className="w-full justify-start gap-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white"
          >
            <Plus size={16} /> New chat
          </Button>
        </div>
        <ScrollArea className="flex-1 px-2 pb-2">
          <div className="space-y-0.5">
            {conversations.map((c) => (
              <div
                key={c.id}
                onClick={() => openConversation(c.id)}
                className={cn(
                  "group flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm cursor-pointer transition-colors",
                  activeId === c.id
                    ? "bg-violet-500/10 text-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground",
                )}
              >
                <MessageSquare size={15} className="shrink-0 opacity-60" />
                <span className="truncate flex-1">{c.title}</span>
                <button
                  onClick={(e) => removeConversation(c.id, e)}
                  className="opacity-0 group-hover:opacity-100 hover:text-destructive transition-opacity"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
            {conversations.length === 0 && (
              <p className="text-xs text-muted-foreground px-3 py-6 text-center">No conversations yet</p>
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Model bar */}
        <div className="h-14 border-b border-border/60 flex items-center px-6 gap-2 shrink-0">
          <span className="text-sm text-muted-foreground mr-1">Model</span>
          {(
            [
              { id: "nexus-chat", label: "Nexus Chat", icon: Bot },
              { id: "nexus-code", label: "Nexus Code", icon: Code2 },
            ] as const
          ).map((m) => (
            <button
              key={m.id}
              onClick={() => setModel(m.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium border transition-all",
                model === m.id
                  ? "border-violet-500/50 bg-violet-500/10 text-violet-600 dark:text-violet-300"
                  : "border-border text-muted-foreground hover:border-violet-500/30 hover:text-foreground",
              )}
            >
              <m.icon size={13} /> {m.label}
            </button>
          ))}
          <button
            onClick={() => setMediaOpen((v) => !v)}
            className={cn(
              "ml-auto flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium border transition-all",
              mediaOpen
                ? "border-violet-500/50 bg-violet-500/10 text-violet-600 dark:text-violet-300"
                : "border-border text-muted-foreground hover:border-violet-500/30 hover:text-foreground",
            )}
          >
            <Images size={13} /> Media
          </button>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1">
          <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
            {routing && (
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground rounded-lg border border-violet-500/25 bg-violet-500/5 px-3 py-2 w-fit">
                <Route size={12} className="text-violet-500 shrink-0" />
                <span>
                  <span className="text-violet-600 dark:text-violet-300 font-medium">{routing.action}</span>
                  {" · "}{routing.policy} · {routing.reason}
                  {routing.self_reflect && " · 🔍 self-reflect"}
                </span>
              </div>
            )}
            {messages.length === 0 && !streaming && (
              <div className="pt-16 text-center">
                <div className="h-14 w-14 mx-auto rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-xl shadow-violet-500/25 mb-5">
                  <Bot className="text-white" size={26} />
                </div>
                <h1 className="text-2xl font-semibold tracking-tight">How can I help?</h1>
                <p className="text-sm text-muted-foreground mt-2 mb-8">
                  Chat and code generation, streamed token-by-token through your own API gateway.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-xl mx-auto text-left">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => send(s)}
                      className="rounded-xl border border-border/70 bg-card/60 px-4 py-3 text-sm text-muted-foreground hover:text-foreground hover:border-violet-500/40 transition-colors"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m, i) => (
              <MessageBubble
                key={i}
                role={m.role}
                content={m.content}
                feedback={feedbackGiven[i]}
                onFeedback={(rating) => {
                  setFeedbackGiven((f) => ({ ...f, [i]: rating }));
                  api.sendFeedback(rating, activeId).catch(() => {});
                }}
              />
            ))}

            {streaming && (
              <MessageBubble role="assistant" content={streamText} pending={streamText.length === 0} status={status} />
            )}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        {/* Composer */}
        <div className="border-t border-border/60 p-4 shrink-0">
          <div className="max-w-3xl mx-auto relative">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={
                forceCode
                  ? "Describe the computation to run in the sandbox…"
                  : forceVideo
                    ? "Describe the video to generate…"
                    : forceImage
                      ? "Describe the image to generate…"
                      : model === "nexus-code"
                        ? "Describe the code you want…"
                        : "Message NexusAI — text, code, images or video…"
              }
              className="min-h-[56px] max-h-40 resize-none pl-[122px] pr-14 rounded-2xl bg-card/60"
              rows={1}
            />
            <Button
              size="icon"
              variant="ghost"
              onClick={() => {
                setForceImage((v) => !v);
                setForceVideo(false);
                setForceCode(false);
              }}
              title={forceImage ? "Image generation: ON" : "Force image generation for this message"}
              className={cn(
                "absolute left-2.5 bottom-2.5 h-9 w-9 rounded-xl transition-colors",
                forceImage ? "bg-violet-500/15 text-violet-500" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <ImagePlus className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => {
                setForceVideo((v) => !v);
                setForceImage(false);
                setForceCode(false);
              }}
              title={forceVideo ? "Video generation: ON" : "Force video generation for this message"}
              className={cn(
                "absolute left-[50px] bottom-2.5 h-9 w-9 rounded-xl transition-colors",
                forceVideo ? "bg-violet-500/15 text-violet-500" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Clapperboard className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              onClick={() => {
                setForceCode((v) => !v);
                setForceImage(false);
                setForceVideo(false);
              }}
              title={forceCode ? "Code sandbox: ON" : "Generate & run code in the sandbox"}
              className={cn(
                "absolute left-[88px] bottom-2.5 h-9 w-9 rounded-xl transition-colors",
                forceCode ? "bg-violet-500/15 text-violet-500" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <SquareTerminal className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              onClick={() => send()}
              disabled={!input.trim() || streaming}
              className="absolute right-2.5 bottom-2.5 h-9 w-9 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white disabled:opacity-40"
            >
              {streaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
          <p className="text-center text-[11px] text-muted-foreground mt-2">
            Enter to send · Shift+Enter for newline ·{" "}
            {forceCode
              ? "⌨️ sandbox mode on"
              : forceVideo
                ? "🎬 video mode on"
                : forceImage
                  ? "🎨 image mode on"
                  : "image/video intent auto-detected"}
          </p>
        </div>
      </div>

      {/* Media preview panel */}
      {mediaOpen && (
        <div className="w-72 shrink-0 border-l border-border/60 flex flex-col bg-card/30">
          <div className="h-14 border-b border-border/60 flex items-center px-4 justify-between shrink-0">
            <span className="text-sm font-medium flex items-center gap-2">
              <Images size={15} className="text-violet-500" /> Generated media
            </span>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setMediaOpen(false)}>
              <X size={14} />
            </Button>
          </div>
          <ScrollArea className="flex-1 p-3">
            {media.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-10">
                Nothing yet — ask NexusAI to draw something.
              </p>
            )}
            <div className="space-y-3">
              {media.map((m) => (
                <div key={m.id} className="group relative rounded-xl overflow-hidden border border-border/60">
                  {m.kind === "video" ? (
                    <video
                      src={m.url}
                      controls
                      playsInline
                      preload="metadata"
                      className="w-full aspect-square object-cover bg-black"
                    />
                  ) : (
                    <img src={m.url} alt={m.prompt} className="w-full aspect-square object-cover" loading="lazy" />
                  )}
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-2.5 pt-6 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
                    <p className="text-[10px] leading-snug text-white/90 line-clamp-3">
                      {m.kind === "video" ? "🎬 " : ""}{m.prompt}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}

function MessageBubble({
  role,
  content,
  pending,
  status,
  feedback,
  onFeedback,
}: {
  role: string;
  content: string;
  pending?: boolean;
  status?: string | null;
  feedback?: number;
  onFeedback?: (rating: number) => void;
}) {
  const isUser = role === "user";
  return (
    <div className={cn("flex gap-3.5 group/msg", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "h-8 w-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
          isUser
            ? "bg-secondary"
            : "bg-gradient-to-br from-violet-500 to-indigo-600 shadow-md shadow-violet-500/20",
        )}
      >
        {isUser ? <UserIcon size={15} /> : <Bot size={15} className="text-white" />}
      </div>
      <div
        className={cn(
          "min-w-0 max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser ? "bg-violet-600 text-white rounded-tr-sm" : "bg-card border border-border/60 rounded-tl-sm",
        )}
      >
        {pending ? (
          <span className="flex items-center gap-2.5 py-1 text-muted-foreground">
            <span className="flex gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-bounce" />
              <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-bounce [animation-delay:0.15s]" />
              <span className="h-1.5 w-1.5 rounded-full bg-violet-500 animate-bounce [animation-delay:0.3s]" />
            </span>
            {status && <span className="text-xs">{status}</span>}
          </span>
        ) : isUser ? (
          <div className="whitespace-pre-wrap">{content}</div>
        ) : (
          <>
            {status && (
              <span className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                <Loader2 className="h-3 w-3 animate-spin" /> {status}
              </span>
            )}
            <Markdown content={content} />
            {onFeedback && content && (
              <div className="flex gap-1 mt-2 opacity-0 group-hover/msg:opacity-100 transition-opacity">
                <button
                  onClick={() => onFeedback(1)}
                  title="Good response"
                  className={cn("p-1 rounded hover:text-violet-500", feedback === 1 && "text-violet-500")}
                >
                  <ThumbsUp size={13} />
                </button>
                <button
                  onClick={() => onFeedback(-1)}
                  title="Bad response"
                  className={cn("p-1 rounded hover:text-destructive", feedback === -1 && "text-destructive")}
                >
                  <ThumbsDown size={13} />
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
