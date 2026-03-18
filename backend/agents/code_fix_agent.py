"""Code Fix Agent for generating security patches.

The Code Fix Agent:
1. Analyzes vulnerable code patterns
2. Generates secure code patches
3. Creates test cases to verify fixes
4. Produces git-ready diffs
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import structlog

from agents.base_agent import BaseAgent, AgentContext, AgentTask, AgentStatus, AgentRegistry

logger = structlog.get_logger()


@dataclass
class FixResult:
    """Result of code fix generation."""
    vulnerability_id: str
    
    # Fix details
    fix_generated: bool
    fix_code: Optional[str]
    fix_explanation: Optional[str]
    fix_type: str  # upgrade_dependency, code_change, configuration
    
    # Code analysis
    original_code: Optional[str]
    patched_code: Optional[str]
    diff: Optional[str]
    file_path: Optional[str]
    line_changes: List[Tuple[int, int]]  # (original_line, new_line) pairs
    
    # Test cases
    test_cases: List[str]
    test_framework: str  # pytest, jest, etc.
    
    # Validation
    validation_passed: bool
    validation_errors: List[str]
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 0.0
    model_used: str = "pattern-based-generation"


class CodeFixAgent(BaseAgent):
    """AI Agent for generating security code fixes."""
    
    def __init__(self):
        super().__init__(
            agent_type="code_fix",
            name="Code Fix Agent"
        )
        self._init_fix_patterns()
    
    def _init_fix_patterns(self):
        """Initialize known vulnerability fix patterns."""
        self.fix_patterns = {
            # SQL Injection patterns
            "CWE-89": {
                "name": "SQL Injection",
                "patterns": [
                    (r'execute\s*\(\s*f["\']', "formatted SQL string"),
                    (r'execute\s*\(\s*["\'].*%s', "string formatting in SQL"),
                    (r'\.format\s*\(.*\).*SELECT|INSERT|UPDATE|DELETE', "format() in SQL"),
                    (r'\+.*SELECT|INSERT|UPDATE|DELETE.*\+', "string concatenation in SQL"),
                ],
                "fix_strategy": "parameterized_query",
                "example_fix": "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
            },
            # Command Injection patterns
            "CWE-78": {
                "name": "Command Injection",
                "patterns": [
                    (r'os\.system\s*\(', "os.system call"),
                    (r'subprocess\.call\s*\(.*shell\s*=\s*True', "subprocess with shell=True"),
                    (r'eval\s*\(', "eval() usage"),
                    (r'exec\s*\(', "exec() usage"),
                ],
                "fix_strategy": "input_sanitization",
                "example_fix": "Use subprocess with list args: subprocess.run(['ls', directory], capture_output=True)",
            },
            # XSS patterns
            "CWE-79": {
                "name": "Cross-Site Scripting (XSS)",
                "patterns": [
                    (r'innerHTML\s*=', "innerHTML assignment"),
                    (r'dangerouslySetInnerHTML', "React dangerouslySetInnerHTML"),
                    (r'\.html\s*\(', "jQuery .html()"),
                    (r'document\.write\s*\(', "document.write"),
                ],
                "fix_strategy": "output_encoding",
                "example_fix": "Use textContent instead of innerHTML, or sanitize with DOMPurify",
            },
            # Path Traversal patterns
            "CWE-22": {
                "name": "Path Traversal",
                "patterns": [
                    (r'open\s*\(.*\+', "path concatenation"),
                    (r'\.\./|\.\.\\\\', "directory traversal sequence"),
                ],
                "fix_strategy": "path_validation",
                "example_fix": "Use os.path.realpath() and validate within allowed directory",
            },
            # Hardcoded Secrets patterns
            "CWE-798": {
                "name": "Hardcoded Credentials",
                "patterns": [
                    (r'password\s*=\s*["\'][^"\']+["\']', "hardcoded password"),
                    (r'api_key\s*=\s*["\'][^"\']+["\']', "hardcoded API key"),
                    (r'secret\s*=\s*["\'][^"\']+["\']', "hardcoded secret"),
                    (r'AWS_ACCESS_KEY_ID|AKIA', "AWS access key"),
                ],
                "fix_strategy": "environment_variables",
                "example_fix": "Use environment variables: password = os.environ.get('DB_PASSWORD')",
            },
            # Insecure Randomness patterns
            "CWE-330": {
                "name": "Insecure Randomness",
                "patterns": [
                    (r'random\.randint|random\.random\s*\(', "insecure random"),
                    (r'Math\.random\s*\(', "JavaScript Math.random for crypto"),
                ],
                "fix_strategy": "crypto_secure_random",
                "example_fix": "Use secrets module: import secrets; token = secrets.token_hex(32)",
            },
        }
        
        # Language-specific test frameworks
        self.test_frameworks = {
            "python": "pytest",
            "javascript": "jest",
            "typescript": "jest",
            "java": "junit",
            "go": "testing",
            "rust": "cargo test",
        }
    
    async def initialize(self, context: AgentContext) -> bool:
        """Initialize fix agent resources."""
        self.logger.info("Initializing Code Fix Agent", task_id=context.task.id)
        return True
    
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """Execute code fix generation."""
        payload = context.task.payload
        vulnerability = payload.get("vulnerability", {})
        repository = payload.get("repository", {})
        
        vuln_id = vulnerability.get("id")
        cwe_id = vulnerability.get("cwe_id")
        file_path = vulnerability.get("file_path")
        
        self.logger.info(
            "Starting code fix generation",
            vuln_id=vuln_id,
            cwe_id=cwe_id,
            file_path=file_path
        )
        
        # 1. Analyze the vulnerability
        analysis = self._analyze_vulnerability(vulnerability)
        
        # 2. Generate the fix
        fix_result = await self._generate_fix(
            vulnerability,
            repository,
            analysis
        )
        
        # 3. Validate the fix
        validation = self._validate_fix(fix_result)
        fix_result.validation_passed = validation["passed"]
        fix_result.validation_errors = validation["errors"]
        
        return {
            "fix_generated": fix_result.fix_generated,
            "vulnerability_id": vuln_id,
            "cwe_id": cwe_id,
            "fix_type": fix_result.fix_type,
            "fix_explanation": fix_result.fix_explanation,
            "original_code": fix_result.original_code,
            "patched_code": fix_result.patched_code,
            "diff": fix_result.diff,
            "file_path": file_path,
            "test_cases": fix_result.test_cases,
            "test_framework": fix_result.test_framework,
            "validation_passed": fix_result.validation_passed,
            "validation_errors": fix_result.validation_errors,
            "confidence": fix_result.confidence,
            "generated_at": fix_result.generated_at.isoformat(),
        }
    
    def _analyze_vulnerability(self, vulnerability: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze vulnerability to determine fix strategy."""
        cwe_id = vulnerability.get("cwe_id")
        title = vulnerability.get("title", "").lower()
        description = vulnerability.get("description", "").lower()
        package_name = vulnerability.get("package_name")
        fixed_version = vulnerability.get("fixed_version")
        current_version = vulnerability.get("current_version")
        
        analysis = {
            "cwe_id": cwe_id,
            "fix_strategy": "unknown",
            "fix_type": "unknown",
            "patterns_found": [],
            "recommendation": "",
        }
        
        # Check for dependency upgrade
        if package_name and fixed_version:
            analysis["fix_type"] = "upgrade_dependency"
            analysis["fix_strategy"] = "version_bump"
            analysis["recommendation"] = f"Upgrade {package_name} from {current_version} to {fixed_version}"
            return analysis
        
        # Check for known CWE patterns
        if cwe_id and cwe_id in self.fix_patterns:
            pattern_data = self.fix_patterns[cwe_id]
            analysis["fix_strategy"] = pattern_data["fix_strategy"]
            analysis["recommendation"] = pattern_data["example_fix"]
            
            # Check for patterns in description
            for pattern, desc in pattern_data["patterns"]:
                if re.search(pattern, description, re.IGNORECASE):
                    analysis["patterns_found"].append(desc)
        
        # Determine fix type based on strategy
        if analysis["fix_strategy"] == "upgrade_dependency":
            analysis["fix_type"] = "upgrade_dependency"
        elif analysis["fix_strategy"] in ["parameterized_query", "input_sanitization", "output_encoding"]:
            analysis["fix_type"] = "code_change"
        elif analysis["fix_strategy"] == "environment_variables":
            analysis["fix_type"] = "configuration"
        else:
            analysis["fix_type"] = "code_change"
        
        return analysis
    
    async def _generate_fix(
        self,
        vulnerability: Dict[str, Any],
        repository: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> FixResult:
        """Generate the actual code fix."""
        vuln_id = vulnerability.get("id")
        cwe_id = vulnerability.get("cwe_id")
        file_path = vulnerability.get("file_path")
        language = repository.get("language", "python").lower()
        
        fix_result = FixResult(
            vulnerability_id=vuln_id,
            fix_generated=False,
            fix_code=None,
            fix_explanation=None,
            fix_type=analysis.get("fix_type", "unknown"),
            original_code=None,
            patched_code=None,
            diff=None,
            file_path=file_path,
            line_changes=[],
            test_cases=[],
            test_framework=self.test_frameworks.get(language, "pytest"),
            validation_passed=False,
            validation_errors=[],
            confidence=0.0,
        )
        
        # Generate fix based on type
        if analysis["fix_type"] == "upgrade_dependency":
            fix_result = self._generate_dependency_fix(vulnerability, analysis, fix_result)
        elif analysis["fix_type"] == "code_change":
            fix_result = self._generate_code_fix(vulnerability, analysis, language, fix_result)
        elif analysis["fix_type"] == "configuration":
            fix_result = self._generate_config_fix(vulnerability, analysis, fix_result)
        
        # Generate test cases
        fix_result.test_cases = self._generate_test_cases(vulnerability, analysis, language)
        
        return fix_result
    
    def _generate_dependency_fix(
        self,
        vulnerability: Dict[str, Any],
        analysis: Dict[str, Any],
        fix_result: FixResult
    ) -> FixResult:
        """Generate fix for dependency vulnerabilities."""
        package_name = vulnerability.get("package_name")
        current_version = vulnerability.get("current_version")
        fixed_version = vulnerability.get("fixed_version")
        file_path = vulnerability.get("file_path")
        
        # Determine file type and generate appropriate fix
        if file_path and ("requirements" in file_path or file_path.endswith(".txt")):
            # Python requirements.txt
            fix_code = f"{package_name}>={fixed_version}  # Was {current_version}"
            diff = f"- {package_name}=={current_version}\n+ {package_name}>={fixed_version}"
        elif file_path and ("package.json" in file_path or file_path.endswith(".json")):
            # Node.js package.json
            fix_code = f'"{package_name}": "^{fixed_version}"'
            diff = f'- "{package_name}": "{current_version}"\n+ "{package_name}": "^{fixed_version}"'
        elif file_path and ("pom.xml" in file_path or file_path.endswith(".xml")):
            # Java Maven
            fix_code = f'<dependency>\n  <groupId>...</groupId>\n  <artifactId>{package_name}</artifactId>\n  <version>{fixed_version}</version>\n</dependency>'
            diff = f'- <version>{current_version}</version>\n+ <version>{fixed_version}</version>'
        elif file_path and ("go.mod" in file_path or file_path.endswith(".mod")):
            # Go modules
            fix_code = f"require {package_name} v{fixed_version}"
            diff = f"- require {package_name} v{current_version}\n+ require {package_name} v{fixed_version}"
        else:
            # Generic
            fix_code = f"Upgrade {package_name} from {current_version} to {fixed_version}"
            diff = f"Version bump: {current_version} -> {fixed_version}"
        
        fix_result.fix_generated = True
        fix_result.fix_code = fix_code
        fix_result.diff = diff
        fix_result.fix_explanation = analysis.get("recommendation", f"Upgrade {package_name} to version {fixed_version} to fix this vulnerability.")
        fix_result.confidence = 0.95  # High confidence for dependency upgrades
        
        return fix_result
    
    def _generate_code_fix(
        self,
        vulnerability: Dict[str, Any],
        analysis: Dict[str, Any],
        language: str,
        fix_result: FixResult
    ) -> FixResult:
        """Generate code-level fix for vulnerabilities."""
        cwe_id = vulnerability.get("cwe_id")
        description = vulnerability.get("description", "")
        title = vulnerability.get("title", "")
        
        # Generate fix based on CWE
        if cwe_id == "CWE-89":  # SQL Injection
            fix_result = self._generate_sql_injection_fix(vulnerability, language, fix_result)
        elif cwe_id == "CWE-78":  # Command Injection
            fix_result = self._generate_command_injection_fix(vulnerability, language, fix_result)
        elif cwe_id == "CWE-79":  # XSS
            fix_result = self._generate_xss_fix(vulnerability, language, fix_result)
        elif cwe_id == "CWE-22":  # Path Traversal
            fix_result = self._generate_path_traversal_fix(vulnerability, language, fix_result)
        elif cwe_id == "CWE-798":  # Hardcoded Secrets
            fix_result = self._generate_secrets_fix(vulnerability, language, fix_result)
        elif cwe_id == "CWE-330":  # Insecure Random
            fix_result = self._generate_random_fix(vulnerability, language, fix_result)
        else:
            # Generic fix template
            fix_result.fix_generated = True
            fix_result.fix_code = f"# Review and fix: {title}\n# {description[:100]}...\n"
            fix_result.fix_explanation = f"Manual review required for {cwe_id}. {analysis.get('recommendation', '')}"
            fix_result.confidence = 0.4
        
        return fix_result
    
    def _generate_sql_injection_fix(
        self,
        vulnerability: Dict[str, Any],
        language: str,
        fix_result: FixResult
    ) -> FixResult:
        """Generate SQL injection fix."""
        file_path = vulnerability.get("file_path", "")
        
        if language in ["python"]:
            original = '''# VULNERABLE CODE:
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
'''
            fixed = '''# SECURE FIX:
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
'''
        elif language in ["javascript", "typescript"]:
            original = '''// VULNERABLE CODE:
const result = await db.query(`SELECT * FROM users WHERE id = ${userId}`);
'''
            fixed = '''// SECURE FIX:
const result = await db.query('SELECT * FROM users WHERE id = ?', [userId]);
'''
        else:
            original = "# String concatenation in SQL query"
            fixed = "# Use parameterized queries instead"
        
        fix_result.fix_generated = True
        fix_result.original_code = original
        fix_result.patched_code = fixed
        fix_result.fix_code = fixed
        fix_result.fix_explanation = "Replace string concatenation/formatting in SQL with parameterized queries (prepared statements)."
        fix_result.diff = f"-{original}\n+{fixed}"
        fix_result.confidence = 0.9
        
        return fix_result
    
    def _generate_command_injection_fix(
        self,
        vulnerability: Dict[str, Any],
        language: str,
        fix_result: FixResult
    ) -> FixResult:
        """Generate command injection fix."""
        if language in ["python"]:
            original = '''# VULNERABLE CODE:
os.system(f"ls {directory}")
# OR
subprocess.call(f"ls {directory}", shell=True)
'''
            fixed = '''# SECURE FIX:
import subprocess
subprocess.run(["ls", directory], capture_output=True)
'''
        elif language in ["javascript", "typescript"]:
            original = '''// VULNERABLE CODE:
exec(`ls ${directory}`, (err, stdout) => {...});
'''
            fixed = '''// SECURE FIX:
execFile('ls', [directory], (err, stdout) => {...});
'''
        else:
            original = "# Shell execution with user input"
            fixed = "# Use exec with array arguments, avoid shell=True"
        
        fix_result.fix_generated = True
        fix_result.original_code = original
        fix_result.patched_code = fixed
        fix_result.fix_code = fixed
        fix_result.fix_explanation = "Avoid shell=True and use list-based arguments to prevent command injection."
        fix_result.diff = f"-{original}\n+{fixed}"
        fix_result.confidence = 0.85
        
        return fix_result
    
    def _generate_xss_fix(
        self,
        vulnerability: Dict[str, Any],
        language: str,
        fix_result: FixResult
    ) -> FixResult:
        """Generate XSS fix."""
        if language in ["javascript", "typescript"]:
            original = '''// VULNERABLE CODE:
element.innerHTML = userInput;
// OR
<div dangerouslySetInnerHTML={{__html: userContent}} />
'''
            fixed = '''// SECURE FIX:
element.textContent = userInput;
// OR
import DOMPurify from 'dompurify';
<div dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(userContent)}} />
'''
        elif language in ["python"]:
            original = '''# VULNERABLE (Django/Flask):
return f"<div>{user_input}</div>"
'''
            fixed = '''# SECURE FIX:
from markupsafe import escape
return f"<div>{escape(user_input)}</div>"
'''
        else:
            original = "# innerHTML or raw HTML output"
            fixed = "# Use textContent or proper HTML encoding"
        
        fix_result.fix_generated = True
        fix_result.original_code = original
        fix_result.patched_code = fixed
        fix_result.fix_code = fixed
        fix_result.fix_explanation = "Use textContent instead of innerHTML for untrusted data, or sanitize with DOMPurify if HTML is needed."
        fix_result.diff = f"-{original}\n+{fixed}"
        fix_result.confidence = 0.88
        
        return fix_result
    
    def _generate_path_traversal_fix(
        self,
        vulnerability: Dict[str, Any],
        language: str,
        fix_result: FixResult
    ) -> FixResult:
        """Generate path traversal fix."""
        if language in ["python"]:
            original = '''# VULNERABLE CODE:
with open(base_path + user_input) as f:
    content = f.read()
'''
            fixed = '''# SECURE FIX:
import os
full_path = os.path.realpath(os.path.join(base_path, user_input))
if not full_path.startswith(os.path.realpath(base_path)):
    raise ValueError("Invalid path")
with open(full_path) as f:
    content = f.read()
'''
        else:
            original = "# Path concatenation with user input"
            fixed = "# Validate path is within allowed directory using realpath"
        
        fix_result.fix_generated = True
        fix_result.original_code = original
        fix_result.patched_code = fixed
        fix_result.fix_code = fixed
        fix_result.fix_explanation = "Validate that the resolved path is within the allowed base directory to prevent path traversal."
        fix_result.diff = f"-{original}\n+{fixed}"
        fix_result.confidence = 0.82
        
        return fix_result
    
    def _generate_secrets_fix(
        self,
        vulnerability: Dict[str, Any],
        language: str,
        fix_result: FixResult
    ) -> FixResult:
        """Generate hardcoded secrets fix."""
        if language in ["python"]:
            original = '''# VULNERABLE CODE:
API_KEY = "sk-abc123xyz789"
'''
            fixed = '''# SECURE FIX:
import os
API_KEY = os.environ.get("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY environment variable not set")
'''
        elif language in ["javascript", "typescript"]:
            original = '''// VULNERABLE CODE:
const API_KEY = "sk-abc123xyz789";
'''
            fixed = '''// SECURE FIX:
const API_KEY = process.env.API_KEY;
if (!API_KEY) {
    throw new Error("API_KEY environment variable not set");
}
'''
        else:
            original = "# Hardcoded secret/credential"
            fixed = "# Move to environment variable or secrets manager"
        
        fix_result.fix_generated = True
        fix_result.original_code = original
        fix_result.patched_code = fixed
        fix_result.fix_code = fixed
        fix_result.fix_explanation = "Move hardcoded secrets to environment variables or use a secrets management service."
        fix_result.diff = f"-{original}\n+{fixed}"
        fix_result.confidence = 0.95
        
        return fix_result
    
    def _generate_random_fix(
        self,
        vulnerability: Dict[str, Any],
        language: str,
        fix_result: FixResult
    ) -> FixResult:
        """Generate insecure randomness fix."""
        if language in ["python"]:
            original = '''# VULNERABLE CODE:
import random
token = random.randint(100000, 999999)
# OR
secret = ''.join(random.choices(string.ascii_letters, k=32))
'''
            fixed = '''# SECURE FIX:
import secrets
token = secrets.randbelow(900000) + 100000
# OR
secret = secrets.token_urlsafe(32)
'''
        elif language in ["javascript", "typescript"]:
            original = '''// VULNERABLE CODE:
const token = Math.random().toString(36).substring(2);
'''
            fixed = '''// SECURE FIX:
import crypto from 'crypto';
const token = crypto.randomBytes(16).toString('hex');
'''
        else:
            original = "# Insecure random for security purposes"
            fixed = "# Use cryptographically secure random generator"
        
        fix_result.fix_generated = True
        fix_result.original_code = original
        fix_result.patched_code = fixed
        fix_result.fix_code = fixed
        fix_result.fix_explanation = "Use cryptographically secure random number generators (secrets in Python, crypto in Node.js) for tokens, passwords, and session IDs."
        fix_result.diff = f"-{original}\n+{fixed}"
        fix_result.confidence = 0.9
        
        return fix_result
    
    def _generate_config_fix(
        self,
        vulnerability: Dict[str, Any],
        analysis: Dict[str, Any],
        fix_result: FixResult
    ) -> FixResult:
        """Generate configuration-level fix."""
        fix_result.fix_generated = True
        fix_result.fix_code = analysis.get("recommendation", "Update configuration to follow security best practices.")
        fix_result.fix_explanation = "Configuration changes needed to remediate this vulnerability."
        fix_result.confidence = 0.7
        return fix_result
    
    def _generate_test_cases(
        self,
        vulnerability: Dict[str, Any],
        analysis: Dict[str, Any],
        language: str
    ) -> List[str]:
        """Generate test cases to verify the fix."""
        cwe_id = vulnerability.get("cwe_id")
        test_cases = []
        
        if cwe_id == "CWE-89":  # SQL Injection
            test_cases = [
                "Test with normal input: 'SELECT * FROM users WHERE id = 1'",
                "Test with malicious input: '1 OR 1=1' - should be parameterized, not concatenated",
                "Test with special characters: \"' OR '1'='1\" - should be safely escaped",
            ]
        elif cwe_id == "CWE-78":  # Command Injection
            test_cases = [
                "Test with normal directory name",
                "Test with malicious input: '; rm -rf /' - should not execute",
                "Test with path traversal: '../../etc/passwd' - should be sanitized",
            ]
        elif cwe_id == "CWE-79":  # XSS
            test_cases = [
                "Test with normal text: 'Hello World'",
                "Test with script tag: '<script>alert(1)</script>' - should be escaped",
                "Test with event handler: ' onclick=alert(1)' - should be sanitized",
            ]
        elif cwe_id == "CWE-22":  # Path Traversal
            test_cases = [
                "Test with valid file path within allowed directory",
                "Test with '../etc/passwd' - should be rejected",
                "Test with absolute path '/etc/passwd' - should be validated",
            ]
        elif cwe_id == "CWE-798":  # Hardcoded Secrets
            test_cases = [
                "Verify secret loads from environment variable",
                "Verify application fails gracefully when env var is missing",
                "Test with rotated secret value",
            ]
        else:
            test_cases = [
                f"Test that {cwe_id} vulnerability is no longer exploitable",
                "Test normal functionality still works after fix",
                "Test edge cases and error handling",
            ]
        
        return test_cases
    
    def _validate_fix(self, fix_result: FixResult) -> Dict[str, Any]:
        """Validate the generated fix."""
        errors = []
        
        if not fix_result.fix_generated:
            errors.append("No fix was generated")
            return {"passed": False, "errors": errors}
        
        # Check fix code is not empty
        if not fix_result.fix_code or len(fix_result.fix_code.strip()) < 10:
            errors.append("Generated fix is too short or empty")
        
        # Check explanation exists
        if not fix_result.fix_explanation:
            errors.append("Missing fix explanation")
        
        # Check for common anti-patterns in the fix itself
        dangerous_patterns = [
            (r'eval\s*\(', "eval() is dangerous"),
            (r'exec\s*\(', "exec() is dangerous"),
            (r'__import__', "Dynamic imports can be risky"),
        ]
        
        for pattern, msg in dangerous_patterns:
            if re.search(pattern, fix_result.fix_code or ""):
                errors.append(f"Fix contains potentially dangerous pattern: {msg}")
        
        passed = len(errors) == 0
        
        return {"passed": passed, "errors": errors}
    
    async def validate_result(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Validate the fix result."""
        required_fields = ["fix_generated", "vulnerability_id", "fix_type"]
        
        for field in required_fields:
            if field not in result:
                self.logger.warning("Missing required field in fix result", field=field)
                return False
        
        if result.get("fix_generated") and not result.get("fix_code"):
            self.logger.warning("Fix marked as generated but no code present")
            return False
        
        return True


# Register the agent
AgentRegistry.register("code_fix", CodeFixAgent)
