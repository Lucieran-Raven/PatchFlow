"""Vulnerability Scanner Service for PatchFlow.

Supports multiple scanners:
- Trivy: Container image and filesystem scanning
- Snyk: Dependency and container scanning (API-based)
- Bandit: Python security linting
- Safety: Python dependency vulnerability checking
"""
import asyncio
import json
import subprocess
import tempfile
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import httpx
from datetime import datetime

logger = structlog.get_logger()


class ScannerType(Enum):
    TRIVY = "trivy"
    SNYK = "snyk"
    BANDIT = "bandit"
    SAFETY = "safety"
    GITHUB_ADVISORY = "github_advisory"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class VulnerabilityFinding:
    """Represents a single vulnerability finding."""
    scanner: ScannerType
    severity: Severity
    title: str
    description: str
    cve_id: Optional[str] = None
    cwe_id: Optional[str] = None
    
    # Location
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    package_name: Optional[str] = None
    installed_version: Optional[str] = None
    fixed_version: Optional[str] = None
    
    # Additional metadata
    references: List[str] = None
    cvss_score: Optional[float] = None
    
    def __post_init__(self):
        if self.references is None:
            self.references = []


@dataclass
class ScanResult:
    """Result of a vulnerability scan."""
    scanner: ScannerType
    target: str  # repo name, image name, etc.
    findings: List[VulnerabilityFinding]
    scan_duration_seconds: float
    scan_started_at: datetime
    scan_completed_at: datetime
    raw_output: Optional[Dict] = None
    error_message: Optional[str] = None
    
    @property
    def has_findings(self) -> bool:
        return len(self.findings) > 0
    
    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.CRITICAL)
    
    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.HIGH)
    
    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.MEDIUM)


class BaseScanner:
    """Base class for vulnerability scanners."""
    
    def __init__(self, scanner_type: ScannerType):
        self.scanner_type = scanner_type
        self.logger = logger.bind(scanner=scanner_type.value)
    
    async def scan_repository(
        self,
        repo_url: str,
        branch: str = "main",
        github_token: Optional[str] = None
    ) -> ScanResult:
        """Scan a GitHub repository for vulnerabilities."""
        raise NotImplementedError
    
    def _severity_from_string(self, severity: str) -> Severity:
        """Convert string severity to enum."""
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "unknown": Severity.UNKNOWN,
            "info": Severity.UNKNOWN,
        }
        return severity_map.get(severity.lower(), Severity.UNKNOWN)


class TrivyScanner(BaseScanner):
    """Trivy vulnerability scanner integration."""
    
    def __init__(self):
        super().__init__(ScannerType.TRIVY)
        self.trivy_available = self._check_trivy()
    
    def _check_trivy(self) -> bool:
        """Check if Trivy is installed."""
        try:
            subprocess.run(["trivy", "--version"], capture_output=True, check=True)
            self.logger.info("Trivy scanner available")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            self.logger.warning("Trivy not installed. Will use fallback scanning.")
            return False
    
    async def scan_repository(
        self,
        repo_url: str,
        branch: str = "main",
        github_token: Optional[str] = None
    ) -> ScanResult:
        """Scan a repository using Trivy filesystem scan."""
        start_time = datetime.utcnow()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone the repository
            clone_url = repo_url
            if github_token:
                # Insert token into URL for private repos
                clone_url = repo_url.replace(
                    "https://github.com/",
                    f"https://{github_token}@github.com/"
                )
            
            try:
                # Clone repository
                self.logger.info("Cloning repository", repo=repo_url, branch=branch)
                clone_result = await asyncio.create_subprocess_exec(
                    "git", "clone", "--depth", "1", "--branch", branch,
                    clone_url, temp_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await clone_result.wait()
                
                if clone_result.returncode != 0:
                    raise Exception(f"Failed to clone repository: {repo_url}")
                
                # Run Trivy scan
                if self.trivy_available:
                    findings = await self._run_trivy_fs_scan(temp_dir)
                else:
                    # Fallback: scan package manifests manually
                    findings = await self._fallback_manifest_scan(temp_dir)
                
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                return ScanResult(
                    scanner=self.scanner_type,
                    target=repo_url,
                    findings=findings,
                    scan_duration_seconds=duration,
                    scan_started_at=start_time,
                    scan_completed_at=end_time
                )
                
            except Exception as e:
                self.logger.error("Scan failed", error=str(e))
                return ScanResult(
                    scanner=self.scanner_type,
                    target=repo_url,
                    findings=[],
                    scan_duration_seconds=0,
                    scan_started_at=start_time,
                    scan_completed_at=datetime.utcnow(),
                    error_message=str(e)
                )
    
    async def _run_trivy_fs_scan(self, repo_path: str) -> List[VulnerabilityFinding]:
        """Run Trivy filesystem scan."""
        findings = []
        
        try:
            # Run Trivy with JSON output
            cmd = [
                "trivy", "fs", "--format", "json",
                "--scanners", "vuln,config,secret",
                "--severity", "UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL",
                repo_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode not in [0, 1]:  # Trivy returns 1 if vulnerabilities found
                self.logger.error("Trivy scan failed", stderr=stderr.decode())
                return findings
            
            # Parse Trivy JSON output
            try:
                results = json.loads(stdout.decode())
            except json.JSONDecodeError:
                self.logger.error("Failed to parse Trivy output")
                return findings
            
            # Extract vulnerabilities from results
            for result in results.get("Results", []):
                for vuln in result.get("Vulnerabilities", []):
                    finding = VulnerabilityFinding(
                        scanner=ScannerType.TRIVY,
                        severity=self._severity_from_string(vuln.get("Severity", "unknown")),
                        title=vuln.get("Title", "Unknown vulnerability"),
                        description=vuln.get("Description", ""),
                        cve_id=vuln.get("VulnerabilityID") if vuln.get("VulnerabilityID", "").startswith("CVE-") else None,
                        package_name=vuln.get("PkgName"),
                        installed_version=vuln.get("InstalledVersion"),
                        fixed_version=vuln.get("FixedVersion"),
                        references=vuln.get("References", [])
                    )
                    findings.append(finding)
                    
        except Exception as e:
            self.logger.error("Trivy scan error", error=str(e))
        
        return findings
    
    async def _fallback_manifest_scan(self, repo_path: str) -> List[VulnerabilityFinding]:
        """Fallback scanning using package manifest analysis."""
        findings = []
        
        # Check for package.json (Node.js)
        package_json_path = os.path.join(repo_path, "package.json")
        if os.path.exists(package_json_path):
            findings.extend(await self._scan_npm_packages(package_json_path))
        
        # Check for requirements.txt (Python)
        requirements_path = os.path.join(repo_path, "requirements.txt")
        if os.path.exists(requirements_path):
            findings.extend(await self._scan_python_packages(requirements_path))
        
        # Check for Cargo.toml (Rust)
        cargo_path = os.path.join(repo_path, "Cargo.toml")
        if os.path.exists(cargo_path):
            findings.extend(await self._scan_cargo_packages(cargo_path))
        
        return findings
    
    async def _scan_npm_packages(self, package_json_path: str) -> List[VulnerabilityFinding]:
        """Scan npm packages for known vulnerabilities (using npm audit)."""
        findings = []
        repo_dir = os.path.dirname(package_json_path)
        
        try:
            # Run npm audit
            process = await asyncio.create_subprocess_exec(
                "npm", "audit", "--json",
                cwd=repo_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            try:
                audit_data = json.loads(stdout.decode())
            except json.JSONDecodeError:
                return findings
            
            # Parse vulnerabilities
            vulnerabilities = audit_data.get("vulnerabilities", {})
            for pkg_name, vuln_data in vulnerabilities.items():
                for via in vuln_data.get("via", []):
                    if isinstance(via, dict):
                        finding = VulnerabilityFinding(
                            scanner=ScannerType.TRIVY,
                            severity=self._severity_from_string(via.get("severity", "unknown")),
                            title=via.get("title", f"Vulnerability in {pkg_name}"),
                            description=via.get("description", ""),
                            cve_id=via.get("cve"),
                            package_name=pkg_name,
                            installed_version=vuln_data.get("range"),
                            fixed_version=via.get("fixAvailable", {}).get("version") if isinstance(via.get("fixAvailable"), dict) else None,
                            references=via.get("url", [])
                        )
                        findings.append(finding)
                        
        except Exception as e:
            self.logger.error("npm audit failed", error=str(e))
        
        return findings
    
    async def _scan_python_packages(self, requirements_path: str) -> List[VulnerabilityFinding]:
        """Scan Python packages using safety check."""
        findings = []
        
        try:
            # Try to run safety check
            process = await asyncio.create_subprocess_exec(
                "safety", "check", "--file", requirements_path, "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return findings  # No vulnerabilities
            
            # Parse safety output
            try:
                safety_data = json.loads(stdout.decode())
                for vuln in safety_data.get("vulnerabilities", []):
                    finding = VulnerabilityFinding(
                        scanner=ScannerType.TRIVY,
                        severity=Severity.HIGH,  # Safety doesn't provide severity
                        title=f"Vulnerability in {vuln.get('package_name')}",
                        description=vuln.get("vulnerability", ""),
                        cve_id=vuln.get("cve"),
                        package_name=vuln.get("package_name"),
                        installed_version=vuln.get("installed_version"),
                        fixed_version=vuln.get("fixed_version")
                    )
                    findings.append(finding)
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            self.logger.error("safety check failed", error=str(e))
        
        return findings
    
    async def _scan_cargo_packages(self, cargo_path: str) -> List[VulnerabilityFinding]:
        """Scan Rust packages using cargo audit."""
        findings = []
        repo_dir = os.path.dirname(cargo_path)
        
        try:
            # Run cargo audit
            process = await asyncio.create_subprocess_exec(
                "cargo", "audit", "--json",
                cwd=repo_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            try:
                audit_data = json.loads(stdout.decode())
                for vuln in audit_data.get("vulnerabilities", []):
                    finding = VulnerabilityFinding(
                        scanner=ScannerType.TRIVY,
                        severity=self._severity_from_string(vuln.get("severity", "unknown")),
                        title=vuln.get("title", "Unknown vulnerability"),
                        description=vuln.get("description", ""),
                        cve_id=vuln.get("cve"),
                        package_name=vuln.get("package", {}).get("name"),
                        installed_version=vuln.get("package", {}).get("version"),
                        fixed_version=vuln.get("patched_versions", ["unknown"])[0] if vuln.get("patched_versions") else None
                    )
                    findings.append(finding)
            except json.JSONDecodeError:
                pass
                
        except Exception as e:
            self.logger.error("cargo audit failed", error=str(e))
        
        return findings


class GitHubAdvisoryScanner(BaseScanner):
    """Scan using GitHub Security Advisory API."""
    
    def __init__(self, github_token: Optional[str] = None):
        super().__init__(ScannerType.GITHUB_ADVISORY)
        self.github_token = github_token
    
    async def scan_repository(
        self,
        repo_url: str,
        branch: str = "main",
        github_token: Optional[str] = None
    ) -> ScanResult:
        """Query GitHub Security Advisories for the repository."""
        start_time = datetime.utcnow()
        token = github_token or self.github_token
        
        if not token:
            return ScanResult(
                scanner=self.scanner_type,
                target=repo_url,
                findings=[],
                scan_duration_seconds=0,
                scan_started_at=start_time,
                scan_completed_at=datetime.utcnow(),
                error_message="GitHub token required for advisory scanning"
            )
        
        findings = []
        
        try:
            # Extract owner/repo from URL
            parts = repo_url.replace("https://github.com/", "").split("/")
            owner, repo = parts[0], parts[1].replace(".git", "")
            
            # Query GitHub GraphQL API for security advisories
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.vix-preview+json"
                }
                
                # Get repository vulnerability alerts
                response = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/dependabot/alerts",
                    headers=headers
                )
                
                if response.status_code == 200:
                    alerts = response.json()
                    
                    for alert in alerts:
                        if alert.get("state") == "open":
                            security_advisory = alert.get("security_advisory", {})
                            
                            finding = VulnerabilityFinding(
                                scanner=ScannerType.GITHUB_ADVISORY,
                                severity=self._severity_from_string(
                                    security_advisory.get("severity", "unknown")
                                ),
                                title=security_advisory.get("summary", "Unknown"),
                                description=security_advisory.get("description", ""),
                                cve_id=next(
                                    (i.get("value") for i in security_advisory.get("identifiers", [])
                                     if i.get("type") == "CVE"),
                                    None
                                ),
                                package_name=alert.get("dependency", {}).get("package", {}).get("name"),
                                installed_version=alert.get("dependency", {}).get("vulnerable_requirements"),
                                fixed_version=alert.get("dependency", {}).get("first_patched_version", {}).get("identifier")
                            )
                            findings.append(finding)
                
        except Exception as e:
            self.logger.error("GitHub advisory scan failed", error=str(e))
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        return ScanResult(
            scanner=self.scanner_type,
            target=repo_url,
            findings=findings,
            scan_duration_seconds=duration,
            scan_started_at=start_time,
            scan_completed_at=end_time
        )


class ScanOrchestrator:
    """Orchestrates multiple scanners and aggregates results."""
    
    def __init__(self):
        self.scanners: Dict[ScannerType, BaseScanner] = {
            ScannerType.TRIVY: TrivyScanner(),
        }
        self.logger = logger
    
    def enable_github_advisory(self, github_token: str):
        """Enable GitHub Security Advisory scanning."""
        self.scanners[ScannerType.GITHUB_ADVISORY] = GitHubAdvisoryScanner(github_token)
    
    async def scan_repository(
        self,
        repo_url: str,
        branch: str = "main",
        github_token: Optional[str] = None,
        scanners: Optional[List[ScannerType]] = None
    ) -> List[ScanResult]:
        """Run multiple scanners on a repository."""
        
        if scanners is None:
            scanners = list(self.scanners.keys())
        
        results = []
        
        for scanner_type in scanners:
            scanner = self.scanners.get(scanner_type)
            if not scanner:
                continue
            
            self.logger.info(
                "Starting scan",
                scanner=scanner_type.value,
                repo=repo_url
            )
            
            try:
                result = await scanner.scan_repository(
                    repo_url=repo_url,
                    branch=branch,
                    github_token=github_token
                )
                results.append(result)
                
                self.logger.info(
                    "Scan completed",
                    scanner=scanner_type.value,
                    findings=len(result.findings),
                    duration=result.scan_duration_seconds
                )
                
            except Exception as e:
                self.logger.error(
                    "Scan failed",
                    scanner=scanner_type.value,
                    error=str(e)
                )
        
        return results
    
    def aggregate_findings(self, results: List[ScanResult]) -> List[VulnerabilityFinding]:
        """Aggregate and deduplicate findings from multiple scanners."""
        all_findings: List[VulnerabilityFinding] = []
        seen: set = set()
        
        for result in results:
            for finding in result.findings:
                # Create deduplication key
                key = (
                    finding.cve_id or finding.title,
                    finding.package_name,
                    finding.file_path
                )
                
                if key not in seen:
                    all_findings.append(finding)
                    seen.add(key)
        
        # Sort by severity
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.UNKNOWN: 4
        }
        
        return sorted(all_findings, key=lambda f: severity_order.get(f.severity, 5))


# Global orchestrator instance
scan_orchestrator = ScanOrchestrator()
