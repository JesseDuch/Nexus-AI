import { NavLink, Outlet, useNavigate } from "react-router";
import { useTheme } from "next-themes";
import {
  MessageSquare,
  KeyRound,
  BarChart3,
  BookOpen,
  LogOut,
  Moon,
  Sun,
  Sparkles,
  Shield,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const NAV = [
  { to: "/", label: "Chat", icon: MessageSquare, end: true },
  { to: "/keys", label: "API Keys", icon: KeyRound },
  { to: "/usage", label: "Usage", icon: BarChart3 },
  { to: "/docs", label: "API Docs", icon: BookOpen },
];

const ADMIN_NAV = { to: "/admin", label: "Admin", icon: Shield };

export default function ConsoleLayout() {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const navigate = useNavigate();

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-border/60 bg-card/50 backdrop-blur flex flex-col">
        <div className="flex items-center gap-2.5 px-5 h-16 border-b border-border/60">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
            <Sparkles className="h-4.5 w-4.5 text-white" size={18} />
          </div>
          <div>
            <div className="font-semibold tracking-tight leading-none">NexusAI</div>
            <div className="text-[11px] text-muted-foreground mt-0.5">OpenAI-compatible platform</div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-violet-500/10 text-violet-600 dark:text-violet-300"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`
              }
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
          {user?.is_admin && (
            <NavLink
              to={ADMIN_NAV.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-violet-500/10 text-violet-600 dark:text-violet-300"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`
              }
            >
              <ADMIN_NAV.icon size={17} />
              {ADMIN_NAV.label}
            </NavLink>
          )}
        </nav>

        <div className="p-3 border-t border-border/60 flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-2.5 rounded-lg px-2 py-2 hover:bg-accent transition-colors flex-1 min-w-0 text-left">
                <Avatar className="h-8 w-8">
                  <AvatarFallback className="bg-gradient-to-br from-violet-500 to-indigo-600 text-white text-xs">
                    {(user?.name || user?.email || "U").slice(0, 2).toUpperCase()}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium truncate">{user?.name || "User"}</div>
                  <div className="text-xs text-muted-foreground truncate">{user?.email}</div>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => {
                  logout();
                  navigate("/auth");
                }}
                className="text-destructive focus:text-destructive"
              >
                <LogOut className="mr-2 h-4 w-4" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </Button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 overflow-hidden flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
