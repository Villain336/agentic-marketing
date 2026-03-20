"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { api } from "@/lib/api";
import { SUPABASE_URL, SUPABASE_ANON_KEY } from "@/lib/constants";

export default function AuthPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-surface-50 flex items-center justify-center">Loading...</div>}>
      <AuthPageInner />
    </Suspense>
  );
}

function AuthPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [mode, setMode] = useState<"login" | "signup">(
    searchParams.get("mode") === "signup" ? "signup" : "login"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agencyName, setAgencyName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const persistSession = (token: string, userId: string) => {
    setAuth(token, userId);
    api.setToken(token);
    localStorage.setItem(
      "omni_session",
      JSON.stringify({ accessToken: token, userId, email, plan: "growth", agencyName: agencyName || "Demo Agency" })
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
        // Demo mode — skip auth, go straight to onboarding
        persistSession("demo", "demo-user");
        router.push("/onboarding");
        return;
      }

      const endpoint =
        mode === "signup"
          ? `${SUPABASE_URL}/auth/v1/signup`
          : `${SUPABASE_URL}/auth/v1/token?grant_type=password`;

      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          apikey: SUPABASE_ANON_KEY,
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error_description || data.msg || "Authentication failed");
        return;
      }

      const token = data.access_token || data.id || "";
      const userId = data.user?.id || data.id || "";
      persistSession(token, userId);

      if (mode === "signup") {
        router.push("/onboarding");
      } else {
        const hasBiz = localStorage.getItem("omni_business");
        router.push(hasBiz ? "/dashboard" : "/onboarding");
      }
    } catch {
      setError("Network error. Using demo mode.");
      persistSession("demo", "demo-user");
      router.push("/onboarding");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-50 flex items-center justify-center px-6">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center">
              <span className="text-white font-bold text-lg">S</span>
            </div>
          </Link>
          <h1 className="font-display font-bold text-2xl text-surface-900">
            {mode === "signup" ? "Create your account" : "Welcome back"}
          </h1>
          <p className="text-sm text-surface-500 mt-2">
            {mode === "signup"
              ? "Start automating your business in 5 minutes"
              : "Log in to your Omni OS dashboard"}
          </p>
        </div>

        <div className="card p-8">
          {/* Tab Switcher */}
          <div className="flex rounded-lg bg-surface-100 p-1 mb-6">
            <button
              onClick={() => setMode("login")}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                mode === "login"
                  ? "bg-white text-surface-900 shadow-sm"
                  : "text-surface-500 hover:text-surface-700"
              }`}
            >
              Log In
            </button>
            <button
              onClick={() => setMode("signup")}
              className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${
                mode === "signup"
                  ? "bg-white text-surface-900 shadow-sm"
                  : "text-surface-500 hover:text-surface-700"
              }`}
            >
              Sign Up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <div>
                <label className="block text-sm font-medium text-surface-700 mb-1.5">
                  Agency / Company Name
                </label>
                <input
                  type="text"
                  value={agencyName}
                  onChange={(e) => setAgencyName(e.target.value)}
                  placeholder="Acme Growth Co"
                  className="input-field"
                />
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-surface-700 mb-1.5">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="input-field"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-surface-700 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="8+ characters"
                className="input-field"
                required
                minLength={8}
              />
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>
            )}

            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? "Please wait..." : mode === "signup" ? "Create Account" : "Log In"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-surface-400 mt-6">
          By continuing, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  );
}
