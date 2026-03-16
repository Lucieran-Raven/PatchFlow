"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Github, LogOut, Loader2, Webhook, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [repos, setRepos] = useState<any[]>([]);
  const [webhookLoading, setWebhookLoading] = useState<string | null>(null);
  const [webhookEvents, setWebhookEvents] = useState<any[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string | null>(null);

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

  const registerWebhook = async (repoId: string) => {
    if (!token) return;
    setWebhookLoading(repoId);
    try {
      const res = await fetch(`http://localhost:8000/webhooks/github/repos/${repoId}/webhook/register`, {
        method: "POST",
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
      });
      if (res.ok) {
        const data = await res.json();
        alert(`✅ Webhook registered! Events: ${data.events.join(", ")}`);
        // Refresh repos to show webhook status
        handleSync();
      } else {
        const err = await res.text();
        alert(`Failed: ${res.status} - ${err}`);
      }
    } catch (e) {
      alert(`Error: ${e}`);
    }
    setWebhookLoading(null);
  };

  const fetchWebhookEvents = async (repoId: string) => {
    if (!token) return;
    setSelectedRepo(repoId);
    try {
      const res = await fetch(`http://localhost:8000/webhooks/github/repos/${repoId}/webhook/events`, {
        headers: { 
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        },
      });
      if (res.ok) {
        const data = await res.json();
        setWebhookEvents(data.events || []);
      }
    } catch (e) {
      console.error("Failed to fetch events:", e);
    }
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
                  <div key={repo.id} className="text-sm border-b pb-2">
                    <div className="flex justify-between items-center">
                      <span className="text-gray-900 font-medium">{repo.full_name}</span>
                      <span className="text-gray-500 text-xs">{repo.language}</span>
                    </div>
                    <div className="flex gap-2 mt-1">
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-6 text-xs"
                        onClick={() => registerWebhook(repo.id)}
                        disabled={webhookLoading === repo.id}
                      >
                        {webhookLoading === repo.id ? (
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        ) : (
                          <Webhook className="h-3 w-3 mr-1" />
                        )}
                        {repo.webhook_id ? "Webhook ✓" : "Enable Webhook"}
                      </Button>
                      {repo.webhook_id && (
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="h-6 text-xs"
                          onClick={() => fetchWebhookEvents(repo.id)}
                        >
                          <Bell className="h-3 w-3 mr-1" />
                          Events
                        </Button>
                      )}
                    </div>
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

          {/* Webhook Events Panel */}
          {selectedRepo && webhookEvents.length > 0 && (
            <div className="bg-white p-6 rounded-lg border border-gray-200 md:col-span-2">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold">Recent Webhook Events</h2>
                <Button variant="ghost" size="sm" onClick={() => setSelectedRepo(null)}>Close</Button>
              </div>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {webhookEvents.map((event) => (
                  <div key={event.id} className="text-sm border-b pb-2">
                    <div className="flex justify-between">
                      <span className="font-medium text-indigo-600">{event.event_type}</span>
                      <span className="text-gray-500 text-xs">
                        {event.received_at ? new Date(event.received_at).toLocaleString() : 'Unknown'}
                      </span>
                    </div>
                    <div className="text-gray-600">
                      {event.pusher_name && <span>By: {event.pusher_name}</span>}
                      {event.ref && <span className="ml-2">Ref: {event.ref.replace('refs/heads/', '')}</span>}
                    </div>
                    {event.commit_message && (
                      <div className="text-gray-500 text-xs truncate">{event.commit_message}</div>
                    )}
                    <div className="flex gap-2 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded ${
                        event.status === 'completed' ? 'bg-green-100 text-green-700' :
                        event.status === 'processing' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {event.status}
                      </span>
                      {event.scan_triggered && (
                        <span className="text-xs px-2 py-0.5 rounded bg-blue-100 text-blue-700">
                          Scan triggered
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
