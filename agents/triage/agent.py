"""Triage Agent - First responder for alert classification."""
from typing import Dict, Any, List
import structlog
from agents import BaseAgent, AgentResult

logger = structlog.get_logger()

class TriageAgent(BaseAgent):
    """
    First responder agent that classifies and prioritizes security alerts.
    
    Model: Fine-tuned Llama 3 70B
    Performance: <500ms per alert
    Output: Prioritized alert with confidence score (0-100)
    """
    
    SEVERITY_WEIGHTS = {
        "critical": 100,
        "high": 75,
        "medium": 50,
        "low": 25
    }
    
    EXPLOITABILITY_FACTORS = {
        "active_exploit": 1.5,
        "poc_available": 1.3,
        "theoretical": 1.0,
        "none": 0.8
    }
    
    def __init__(self):
        super().__init__("Triage Agent", "triage")
    
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Triage a new security alert.
        
        Args:
            context: {
                "alert": {
                    "title": str,
                    "description": str,
                    "cve_id": str (optional),
                    "severity": str,
                    "scanner": str,
                    "repository_id": str,
                    "file_path": str (optional),
                    "line_number": int (optional)
                }
            }
        """
        alert = context.get("alert", {})
        
        try:
            # Calculate base severity score
            severity = alert.get("severity", "low").lower()
            base_score = self.SEVERITY_WEIGHTS.get(severity, 25)
            
            # Apply exploitability factor
            exploit_status = alert.get("exploit_status", "none")
            exploit_factor = self.EXPLOITABILITY_FACTORS.get(exploit_status, 1.0)
            
            # Calculate confidence score
            confidence = min(100, int(base_score * exploit_factor))
            
            # Determine if auto-fix threshold is met
            auto_fix_threshold = 90
            should_auto_fix = confidence >= auto_fix_threshold and severity in ["critical", "high"]
            
            result = {
                "alert_id": alert.get("id"),
                "severity": severity,
                "confidence_score": confidence,
                "priority": self._calculate_priority(confidence),
                "should_auto_remediate": should_auto_fix,
                "auto_fix_threshold": auto_fix_threshold,
                "assigned_agents": self._assign_agents(severity, should_auto_fix),
                "estimated_fix_time": self._estimate_fix_time(severity, alert.get("file_path")),
                "triage_reasoning": self._generate_reasoning(alert, confidence)
            }
            
            return AgentResult(
                success=True,
                data=result,
                confidence=confidence / 100.0
            )
            
        except Exception as e:
            logger.error("Triage failed", error=str(e))
            return AgentResult(
                success=False,
                data={},
                error=str(e)
            )
    
    def _calculate_priority(self, confidence: int) -> str:
        """Calculate priority based on confidence score."""
        if confidence >= 95:
            return "p0"
        elif confidence >= 80:
            return "p1"
        elif confidence >= 60:
            return "p2"
        else:
            return "p3"
    
    def _assign_agents(self, severity: str, auto_fix: bool) -> List[str]:
        """Determine which agents should handle this alert."""
        agents = ["investigation"]
        
        if severity in ["critical", "high"]:
            agents.append("threat_intel")
        
        if auto_fix:
            agents.extend(["code_fix", "remediation", "rollback"])
        
        return agents
    
    def _estimate_fix_time(self, severity: str, file_path: str = None) -> str:
        """Estimate time to fix based on severity and file type."""
        if severity == "critical":
            return "5-15 minutes"
        elif severity == "high":
            return "15-30 minutes"
        elif severity == "medium":
            return "30-60 minutes"
        else:
            return "1-4 hours"
    
    def _generate_reasoning(self, alert: Dict, confidence: int) -> str:
        """Generate human-readable triage reasoning."""
        cve = alert.get("cve_id", "N/A")
        severity = alert.get("severity", "unknown")
        scanner = alert.get("scanner", "unknown")
        
        return (
            f"Alert from {scanner} with {severity} severity (CVE: {cve}). "
            f"Confidence score of {confidence} based on severity weighting and "
            f"known exploitability factors."
        )
