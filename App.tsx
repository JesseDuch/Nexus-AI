import { Navigate, Route, Routes, useLocation } from "react-router";
import { ThemeProvider } from "next-themes";
import { AuthProvider, useAuth } from "@/lib/auth";
import ConsoleLayout from "@/components/ConsoleLayout";
import AuthPage from "@/pages/AuthPage";
import ChatPage from "@/pages/ChatPage";
import KeysPage from "@/pages/KeysPage";
import UsagePage from "@/pages/UsagePage";
import DocsPage from "@/pages/DocsPage";
import AdminPage from "@/pages/AdminPage";
import type { ReactNode } from "react";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 animate-pulse" />
      </div>
    );
  }
  if (!user) return <Navigate to="/auth" state={{ from: location }} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
      <AuthProvider>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route
            element={
              <RequireAuth>
                <ConsoleLayout />
              </RequireAuth>
            }
          >
            <Route path="/" element={<ChatPage />} />
            <Route path="/keys" element={<KeysPage />} />
            <Route path="/usage" element={<UsagePage />} />
            <Route path="/docs" element={<DocsPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </ThemeProvider>
  );
}
