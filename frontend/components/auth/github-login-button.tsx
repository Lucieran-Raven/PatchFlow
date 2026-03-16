"use client";

import { Button } from "@/components/ui/button";
import { Github } from "lucide-react";

export function GitHubLoginButton() {
  const handleLogin = () => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.location.href = `${apiUrl}/auth/github/login`;
  };

  return (
    <Button 
      onClick={handleLogin}
      className="bg-gray-900 hover:bg-gray-800 text-white"
    >
      <Github className="w-4 h-4 mr-2" />
      Login with GitHub
    </Button>
  );
}
