"""Triage Agent for vulnerability analysis and prioritization.

The Triage Agent analyzes security vulnerabilities to:
1. Assess risk severity with context
2. Identify exploitation vectors
3. Determine fix priority
4. Generate remediation recommendations
"""
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import structlog

from agents.base_agent import BaseAgent, AgentContext, AgentTask, AgentStatus, AgentRegistry
from models import Vulnerability, Repository

logger = structlog.get_logger()


@dataclass
class TriageResult:
    """Result of vulnerability triage analysis."""
    vulnerability_id: str
    
    # Risk Assessment
    risk_score: float  # 0-100
    risk_level: str  # critical, high, medium, low
    
    # Context Analysis
    is_exploitable: bool
    exploit_difficulty: str  # easy, moderate, hard
    attack_vector: str
    
    # Impact Assessment
    impact_confidentiality: bool
    impact_integrity: bool
    impact_availability: bool
    business_impact: str
    
    # Prioritization
    priority_score: float  # 0-100
    recommended_action: str  # immediate, scheduled, backlog
    sla_hours: int
    
    # Fix Recommendation
    fix_complexity: str  # simple, moderate, complex
    estimated_fix_time: str
    fix_approach: str
    
    # Analysis metadata
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
    model_used: str = "context-aware-scoring"
    confidence: float = 0.0


class TriageAgent(BaseAgent):
    """AI Agent for vulnerability triage and prioritization."""
    
    def __init__(self):
        super().__init__(
            agent_type="triage",
            name="Vulnerability Triage Agent"
        )
        self.scoring_weights = {
            "cvss_base": 0.30,
            "exploitability": 0.25,
            "asset_criticality": 0.20,
            "exposure": 0.15,
            "data_classification": 0.10
        }
    
    async def initialize(self, context: AgentContext) -> bool:
        """Initialize triage resources."""
        self.logger.info("Initializing Triage Agent", task_id=context.task.id)
        # Load any necessary models or configs
        return True
    
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """Execute vulnerability triage analysis."""
        payload = context.task.payload
        vulnerability_data = payload.get("vulnerability", {})
        repository_data = payload.get("repository", {})
        
        self.logger.info(
            "Starting vulnerability triage",
            vuln_id=vulnerability_data.get("id"),
            cve_id=vulnerability_data.get("cve_id")
        )
        
        # Run triage analysis
        triage_result = await self._analyze_vulnerability(
            vulnerability_data,
            repository_data
        )
        
        return {
            "triage_completed": True,
            "vulnerability_id": triage_result.vulnerability_id,
            "risk_score": triage_result.risk_score,
            "risk_level": triage_result.risk_level,
            "priority_score": triage_result.priority_score,
            "recommended_action": triage_result.recommended_action,
            "sla_hours": triage_result.sla_hours,
            "is_exploitable": triage_result.is_exploitable,
            "exploit_difficulty": triage_result.exploit_difficulty,
            "attack_vector": triage_result.attack_vector,
            "business_impact": triage_result.business_impact,
            "fix_complexity": triage_result.fix_complexity,
            "estimated_fix_time": triage_result.estimated_fix_time,
            "fix_approach": triage_result.fix_approach,
            "impact_confidentiality": triage_result.impact_confidentiality,
            "impact_integrity": triage_result.impact_integrity,
            "impact_availability": triage_result.impact_availability,
            "analyzed_at": triage_result.analyzed_at.isoformat(),
            "confidence": triage_result.confidence
        }
    
    async def _analyze_vulnerability(
        self,
        vuln_data: Dict[str, Any],
        repo_data: Dict[str, Any]
    ) -> TriageResult:
        """Perform comprehensive vulnerability analysis."""
        
        vuln_id = vuln_data.get("id", "unknown")
        severity = vuln_data.get("severity", "unknown")
        cve_id = vuln_data.get("cve_id")
        cwe_id = vuln_data.get("cwe_id")
        package_name = vuln_data.get("package_name")
        
        # 1. Calculate base risk score from severity
        base_score = self._severity_to_score(severity)
        
        # 2. Assess exploitability
        is_exploitable, exploit_difficulty, attack_vector = self._assess_exploitability(
            vuln_data, cve_id, cwe_id
        )
        
        # 3. Determine impact on CIA triad
        impact_conf, impact_integ, impact_avail = self._assess_impact(
            vuln_data, cwe_id
        )
        
        # 4. Calculate business impact
        business_impact = self._calculate_business_impact(
            vuln_data, repo_data, impact_conf, impact_integ, impact_avail
        )
        
        # 5. Calculate final risk score
        risk_score = self._calculate_risk_score(
            base_score=base_score,
            is_exploitable=is_exploitable,
            exploit_difficulty=exploit_difficulty,
            impact_conf=impact_conf,
            impact_integ=impact_integ,
            impact_avail=impact_avail,
            repo_data=repo_data
        )
        
        # 6. Determine risk level
        risk_level = self._score_to_risk_level(risk_score)
        
        # 7. Calculate priority and SLA
        priority_score, recommended_action, sla_hours = self._calculate_priority(
            risk_score, is_exploitable, exploit_difficulty, repo_data
        )
        
        # 8. Assess fix complexity
        fix_complexity, fix_time, fix_approach = self._assess_fix_complexity(
            vuln_data, package_name
        )
        
        return TriageResult(
            vulnerability_id=vuln_id,
            risk_score=round(risk_score, 1),
            risk_level=risk_level,
            is_exploitable=is_exploitable,
            exploit_difficulty=exploit_difficulty,
            attack_vector=attack_vector,
            impact_confidentiality=impact_conf,
            impact_integrity=impact_integ,
            impact_availability=impact_avail,
            business_impact=business_impact,
            priority_score=round(priority_score, 1),
            recommended_action=recommended_action,
            sla_hours=sla_hours,
            fix_complexity=fix_complexity,
            estimated_fix_time=fix_time,
            fix_approach=fix_approach,
            confidence=0.85  # Context-aware confidence
        )
    
    def _severity_to_score(self, severity: str) -> float:
        """Convert severity string to base score."""
        scores = {
            "critical": 95.0,
            "high": 75.0,
            "medium": 50.0,
            "low": 25.0,
            "unknown": 40.0
        }
        return scores.get(severity.lower(), 40.0)
    
    def _assess_exploitability(
        self,
        vuln_data: Dict[str, Any],
        cve_id: Optional[str],
        cwe_id: Optional[str]
    ) -> Tuple[bool, str, str]:
        """Assess how easily the vulnerability can be exploited."""
        
        # Check for known exploits
        has_known_exploit = vuln_data.get("has_exploit", False)
        
        # Analyze CWE patterns
        easy_cwes = ["CWE-78", "CWE-89", "CWE-94", "CWE-91"]  # Injection, RCE
        medium_cwes = ["CWE-79", "CWE-22", "CWE-20"]  # XSS, Path Traversal
        
        if cwe_id in easy_cwes:
            difficulty = "easy"
            exploitable = True
        elif cwe_id in medium_cwes:
            difficulty = "moderate"
            exploitable = True
        else:
            difficulty = "hard"
            exploitable = has_known_exploit
        
        # Determine attack vector
        description = vuln_data.get("description", "").lower()
        if "remote" in description or "network" in description:
            vector = "remote"
        elif "local" in description:
            vector = "local"
        elif "authenticated" in description or "admin" in description:
            vector = "authenticated"
        else:
            vector = "unknown"
        
        return exploitable, difficulty, vector
    
    def _assess_impact(
        self,
        vuln_data: Dict[str, Any],
        cwe_id: Optional[str]
    ) -> Tuple[bool, bool, bool]:
        """Assess impact on Confidentiality, Integrity, Availability."""
        
        description = vuln_data.get("description", "").lower()
        title = vuln_data.get("title", "").lower()
        combined = f"{title} {description}"
        
        # Confidentiality impact
        conf_impact = any(term in combined for term in [
            "disclosure", "leak", "expose", "read", "access", "information"
        ])
        
        # Integrity impact
        integ_impact = any(term in combined for term in [
            "modify", "tamper", "inject", "forge", "spoof", "write"
        ])
        
        # Availability impact
        avail_impact = any(term in combined for term in [
            "denial", "crash", "hang", "infinite", "loop", "dos", "ddos"
        ])
        
        # CWE-based adjustments
        if cwe_id in ["CWE-200", "CWE-201", "CWE-209"]:
            conf_impact = True
        elif cwe_id in ["CWE-345", "CWE-354", "CWE-358"]:
            integ_impact = True
        elif cwe_id in ["CWE-400", "CWE-770"]:
            avail_impact = True
        
        return conf_impact, integ_impact, avail_impact
    
    def _calculate_business_impact(
        self,
        vuln_data: Dict[str, Any],
        repo_data: Dict[str, Any],
        impact_conf: bool,
        impact_integ: bool,
        impact_avail: bool
    ) -> str:
        """Calculate business impact based on vulnerability context."""
        
        # Check if it's a production system
        is_production = repo_data.get("is_production", True)
        
        # Check data sensitivity
        is_private = repo_data.get("is_private", False)
        has_sensitive_data = repo_data.get("has_sensitive_data", True)
        
        # Calculate impact score
        impact_score = 0
        if impact_conf:
            impact_score += 30
        if impact_integ:
            impact_score += 35
        if impact_avail:
            impact_score += 20
        
        if is_production:
            impact_score += 15
        if is_private and has_sensitive_data:
            impact_score += 10
        
        # Determine business impact level
        if impact_score >= 80:
            return "critical"
        elif impact_score >= 60:
            return "high"
        elif impact_score >= 40:
            return "medium"
        else:
            return "low"
    
    def _calculate_risk_score(
        self,
        base_score: float,
        is_exploitable: bool,
        exploit_difficulty: str,
        impact_conf: bool,
        impact_integ: bool,
        impact_avail: bool,
        repo_data: Dict[str, Any]
    ) -> float:
        """Calculate final risk score using weighted factors."""
        
        # Start with base score
        score = base_score * self.scoring_weights["cvss_base"]
        
        # Exploitability factor
        exploit_multiplier = {
            "easy": 1.0,
            "moderate": 0.7,
            "hard": 0.4
        }
        if is_exploitable:
            score += (25 * exploit_multiplier[exploit_difficulty] * 
                     self.scoring_weights["exploitability"])
        
        # Impact factors
        impact_score = 0
        if impact_conf:
            impact_score += 25
        if impact_integ:
            impact_score += 30
        if impact_avail:
            impact_score += 20
        
        score += impact_score * self.scoring_weights["asset_criticality"]
        
        # Exposure factor (public repos are more exposed)
        if not repo_data.get("is_private", False):
            score += 15 * self.scoring_weights["exposure"]
        
        # Cap at 100
        return min(score, 100.0)
    
    def _score_to_risk_level(self, score: float) -> str:
        """Convert numeric score to risk level."""
        if score >= 80:
            return "critical"
        elif score >= 60:
            return "high"
        elif score >= 40:
            return "medium"
        elif score >= 20:
            return "low"
        else:
            return "informational"
    
    def _calculate_priority(
        self,
        risk_score: float,
        is_exploitable: bool,
        exploit_difficulty: str,
        repo_data: Dict[str, Any]
    ) -> Tuple[float, str, int]:
        """Calculate priority score and SLA."""
        
        # Priority is heavily weighted by risk and exploitability
        priority = risk_score * 0.6
        
        if is_exploitable:
            if exploit_difficulty == "easy":
                priority += 25
            elif exploit_difficulty == "moderate":
                priority += 15
            else:
                priority += 5
        
        # Production systems get higher priority
        if repo_data.get("is_production", True):
            priority += 10
        
        # Determine action and SLA
        if priority >= 85:
            return priority, "immediate", 24
        elif priority >= 65:
            return priority, "scheduled", 72
        elif priority >= 40:
            return priority, "scheduled", 168  # 1 week
        else:
            return priority, "backlog", 720  # 30 days
    
    def _assess_fix_complexity(
        self,
        vuln_data: Dict[str, Any],
        package_name: Optional[str]
    ) -> Tuple[str, str, str]:
        """Assess the complexity of fixing the vulnerability."""
        
        severity = vuln_data.get("severity", "unknown")
        fixed_version = vuln_data.get("fixed_version")
        current_version = vuln_data.get("current_version")
        
        # Simple case: version bump available
        if fixed_version and package_name:
            # Check if it's a major version change
            try:
                current_parts = current_version.split('.')
                fixed_parts = fixed_version.split('.')
                if current_parts[0] == fixed_parts[0]:
                    return "simple", "1-2 hours", "upgrade_dependency"
                else:
                    return "moderate", "4-8 hours", "upgrade_dependency_major"
            except:
                return "simple", "1-2 hours", "upgrade_dependency"
        
        # Complex case: requires code changes
        description = vuln_data.get("description", "").lower()
        
        if severity == "critical":
            return "complex", "1-3 days", "code_remediation"
        elif severity == "high":
            return "moderate", "4-8 hours", "patch_and_test"
        else:
            return "simple", "1-2 hours", "standard_update"
    
    async def validate_result(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Validate triage result has all required fields."""
        required_fields = [
            "risk_score", "risk_level", "priority_score",
            "recommended_action", "is_exploitable"
        ]
        
        for field in required_fields:
            if field not in result:
                self.logger.warning("Missing required field in triage result", field=field)
                return False
        
        # Validate score ranges
        if not (0 <= result.get("risk_score", 0) <= 100):
            return False
        if not (0 <= result.get("priority_score", 0) <= 100):
            return False
        
        return True


# Register the agent
AgentRegistry.register("triage", TriageAgent)
