"use client"

import { Button } from "@/components/ui/button"
import { Shield, Zap, Clock, CheckCircle, ArrowRight, Github, Slack, Lock } from "lucide-react"
import { GitHubLoginButton } from "@/components/auth/github-login-button"

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      {/* Navigation */}
      <nav className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-2">
              <Shield className="h-8 w-8 text-indigo-600" />
              <span className="text-xl font-bold text-slate-900">PatchFlow</span>
            </div>
            <div className="hidden md:flex items-center space-x-8">
              <a href="#features" className="text-slate-600 hover:text-slate-900">Features</a>
              <a href="#how-it-works" className="text-slate-600 hover:text-slate-900">How It Works</a>
              <a href="#pricing" className="text-slate-600 hover:text-slate-900">Pricing</a>
              <GitHubLoginButton />
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-20 pb-16 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center px-4 py-2 rounded-full bg-indigo-100 text-indigo-700 text-sm font-medium mb-8">
            <Zap className="h-4 w-4 mr-2" />
            Now in Public Beta
          </div>
          <h1 className="text-5xl md:text-7xl font-bold text-slate-900 mb-6 leading-tight">
            Security That<br />
            <span className="text-indigo-600">Fixes Itself</span>
          </h1>
          <p className="text-xl md:text-2xl text-slate-600 max-w-3xl mx-auto mb-10">
            Autonomous AI security engineer that finds vulnerabilities, generates fixes, 
            and deploys them automatically. Reduce security debt by 75% in 24 hours.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="lg" className="bg-indigo-600 hover:bg-indigo-700 text-lg px-8">
              Start Free Trial
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button size="lg" variant="outline" className="text-lg px-8">
              <Github className="mr-2 h-5 w-5" />
              View on GitHub
            </Button>
          </div>
          <p className="mt-4 text-sm text-slate-500">No credit card required. 14-day free trial.</p>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-12 bg-white border-y border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <div className="text-4xl font-bold text-indigo-600">75%</div>
              <div className="text-slate-600 mt-1">Debt Reduction</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-indigo-600">&lt;4hrs</div>
              <div className="text-slate-600 mt-1">Mean Time to Remediate</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-indigo-600">95%</div>
              <div className="text-slate-600 mt-1">Fix Success Rate</div>
            </div>
            <div>
              <div className="text-4xl font-bold text-indigo-600">1M+</div>
              <div className="text-slate-600 mt-1">Vulnerabilities Fixed</div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              End-to-End Autonomous Security
            </h2>
            <p className="text-xl text-slate-600 max-w-3xl mx-auto">
              12 AI agents work together to detect, analyze, fix, and deploy security patches automatically.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<Shield className="h-8 w-8 text-indigo-600" />}
              title="Autonomous Detection"
              description="Connect your repos and let our AI triage agent analyze every vulnerability with 94%+ confidence scoring."
            />
            <FeatureCard 
              icon={<Zap className="h-8 w-8 text-indigo-600" />}
              title="Intelligent Remediation"
              description="Code Fix Agent generates working patches with test cases, validated against your CI/CD pipeline."
            />
            <FeatureCard 
              icon={<Clock className="h-8 w-8 text-indigo-600" />}
              title="Zero-Touch Deployment"
              description="Automatically create PRs, get approvals, merge changes, and monitor with built-in rollback protection."
            />
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="py-20 bg-slate-50 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              From Vulnerability to Fixed in Minutes
            </h2>
          </div>
          <div className="grid md:grid-cols-5 gap-4">
            <StepCard number="1" title="Connect" description="Link GitHub/GitLab repos in seconds" />
            <StepCard number="2" title="Detect" description="AI agents scan for vulnerabilities" />
            <StepCard number="3" title="Analyze" description="Root cause investigation & risk scoring" />
            <StepCard number="4" title="Fix" description="Auto-generate patches with tests" />
            <StepCard number="5" title="Deploy" description="Create PR, merge, monitor" />
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-4">
              Simple, Transparent Pricing
            </h2>
            <p className="text-xl text-slate-600">
              Start free, scale as you grow. ROI positive from day one.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
            <PricingCard 
              tier="Startup"
              price="$500"
              description="For small teams getting started"
              features={["Up to 50 repositories", "Basic auto-fix", "Email support", "Slack notifications"]}
              cta="Start Free Trial"
              popular={false}
            />
            <PricingCard 
              tier="Growth"
              price="$2,500"
              description="For growing engineering teams"
              features={["Up to 500 repositories", "Full agent stack", "Slack support", "Custom policies", "Audit logs"]}
              cta="Start Free Trial"
              popular={true}
            />
            <PricingCard 
              tier="Enterprise"
              price="Custom"
              description="For large organizations"
              features={["Unlimited repositories", "Custom AI models", "On-premise deployment", "24/7 support", "SSO & compliance"]}
              cta="Contact Sales"
              popular={false}
            />
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 bg-indigo-600 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">
            Ready to Make Security Debt Obsolete?
          </h2>
          <p className="text-xl text-indigo-100 mb-8">
            Join 500+ engineering teams who fixed 1,000,000+ vulnerabilities with PatchFlow.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Button size="lg" className="bg-white text-indigo-600 hover:bg-indigo-50 text-lg px-8">
              Get Started Free
              <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
            <Button size="lg" variant="outline" className="border-white text-white hover:bg-white/10 text-lg px-8">
              Schedule Demo
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 bg-slate-900 text-slate-300 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center space-x-2 mb-4">
                <Shield className="h-6 w-6 text-indigo-400" />
                <span className="text-lg font-bold text-white">PatchFlow</span>
              </div>
              <p className="text-sm">
                Autonomous AI security engineer that fixes vulnerabilities automatically.
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white">Features</a></li>
                <li><a href="#" className="hover:text-white">Integrations</a></li>
                <li><a href="#" className="hover:text-white">Pricing</a></li>
                <li><a href="#" className="hover:text-white">Changelog</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Resources</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white">Documentation</a></li>
                <li><a href="#" className="hover:text-white">API Reference</a></li>
                <li><a href="#" className="hover:text-white">Blog</a></li>
                <li><a href="#" className="hover:text-white">Community</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white">About</a></li>
                <li><a href="#" className="hover:text-white">Careers</a></li>
                <li><a href="#" className="hover:text-white">Security</a></li>
                <li><a href="#" className="hover:text-white">Contact</a></li>
              </ul>
            </div>
          </div>
          <div className="border-t border-slate-800 pt-8 flex flex-col md:flex-row justify-between items-center">
            <p className="text-sm">© 2026 PatchFlow Inc. All rights reserved.</p>
            <div className="flex items-center space-x-6 mt-4 md:mt-0">
              <a href="#" className="hover:text-white"><Github className="h-5 w-5" /></a>
              <a href="#" className="hover:text-white"><Slack className="h-5 w-5" /></a>
              <a href="#" className="hover:text-white"><Lock className="h-5 w-5" /></a>
            </div>
          </div>
        </div>
      </footer>
    </main>
  )
}

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
      <div className="mb-4">{icon}</div>
      <h3 className="text-xl font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-slate-600">{description}</p>
    </div>
  )
}

function StepCard({ number, title, description }: { number: string, title: string, description: string }) {
  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 text-center">
      <div className="w-12 h-12 bg-indigo-100 text-indigo-600 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
        {number}
      </div>
      <h3 className="text-lg font-semibold text-slate-900 mb-1">{title}</h3>
      <p className="text-sm text-slate-600">{description}</p>
    </div>
  )
}

function PricingCard({ tier, price, description, features, cta, popular }: { 
  tier: string, 
  price: string, 
  description: string, 
  features: string[], 
  cta: string,
  popular: boolean 
}) {
  return (
    <div className={`p-8 rounded-xl border ${popular ? 'border-indigo-600 ring-2 ring-indigo-600' : 'border-slate-200'} bg-white relative`}>
      {popular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-indigo-600 text-white text-sm font-medium px-4 py-1 rounded-full">
          Most Popular
        </div>
      )}
      <h3 className="text-xl font-semibold text-slate-900 mb-2">{tier}</h3>
      <div className="mb-4">
        <span className="text-4xl font-bold text-slate-900">{price}</span>
        {price !== "Custom" && <span className="text-slate-600">/month</span>}
      </div>
      <p className="text-slate-600 mb-6">{description}</p>
      <ul className="space-y-3 mb-8">
        {features.map((feature, i) => (
          <li key={i} className="flex items-center text-sm text-slate-600">
            <CheckCircle className="h-4 w-4 text-indigo-600 mr-2 flex-shrink-0" />
            {feature}
          </li>
        ))}
      </ul>
      <Button className={`w-full ${popular ? 'bg-indigo-600 hover:bg-indigo-700' : ''}`}>
        {cta}
      </Button>
    </div>
  )
}
