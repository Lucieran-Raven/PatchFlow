"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Github, LogOut, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [repos, setRepos] = useState<any[]>([]);

  useEffect(() => {
    const stored = localStorage.getItem("patchflow_token");
    if (!stored) {
      router.push("/");
    } else {
      setToken(stored);
    }
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem("patchflow_token");
    router.push("/");
  };

  const handleSync = async () => {
    if (!token) return;
    setSyncing(true);
    try {
      const res = await fetch("http://localhost:8000/auth/github/repos", {
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
      });
      if (res.ok) {
        const data = await res.json();
        console.log("API Response:", data);
        setRepos(data.repositories || []);
      } else {
        const err = await res.text();
        alert(`Failed: ${res.status} - ${err}`);
      }
    } catch (e) {
      alert(`Error: ${e}`);
    }
    setSyncing(false);
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gray-900"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <Shield className="h-8 w-8 text-indigo-600" />
              <span className="text-xl font-bold text-gray-900">PatchFlow</span>
            </div>
            <Button variant="outline" onClick={handleLogout}>
              <LogOut className="h-4 w-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">Dashboard</h1>
        
        <div className="grid md:grid-cols-2 gap-6">
          {/* GitHub Connection Card */}
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <div className="flex items-center space-x-3 mb-4">
              <Github className="h-6 w-6 text-gray-900" />
              <h2 className="text-lg font-semibold">GitHub Connected</h2>
            </div>
            <p className="text-gray-600 mb-4">
              Your GitHub account is connected. {repos.length > 0 ? `${repos.length} repos synced.` : "Repositories will appear here once synced."}
            </p>
            <Button variant="outline" className="w-full" onClick={handleSync} disabled={syncing}>
              {syncing ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {syncing ? "Syncing..." : "Sync Repositories"}
            </Button>
            
            {repos.length > 0 && (
              <div className="mt-4 space-y-2">
                <h3 className="font-medium text-sm text-gray-700">Your Repositories:</h3>
                {repos.slice(0, 5).map((repo) => (
                  <div key={repo.id} className="text-sm text-gray-600 border-b pb-1">
                    {repo.full_name} {repo.language && `(${repo.language})`}
                  </div>
                ))}
                {repos.length > 5 && <div className="text-sm text-gray-500">+{repos.length - 5} more...</div>}
              </div>
            )}
          </div>

          {/* Getting Started Card */}
          <div className="bg-white p-6 rounded-lg border border-gray-200">
            <h2 className="text-lg font-semibold mb-4">Getting Started</h2>
            <ul className="space-y-3 text-gray-600">
              <li className="flex items-center">
                <span className="text-green-500 mr-2">✓</span>
                Connect GitHub account
              </li>
              <li className="flex items-center">
                <span className={repos.length > 0 ? "text-green-500 mr-2" : "text-gray-400 mr-2"}>
                  {repos.length > 0 ? "✓" : "○"}
                </span>
                Add repositories to scan
              </li>
              <li className="flex items-center">
                <span className="text-gray-400 mr-2">○</span>
                Review vulnerability findings
              </li>
              <li className="flex items-center">
                <span className="text-gray-400 mr-2">○</span>
                Enable auto-fix for critical issues
              </li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}
