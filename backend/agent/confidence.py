"""
CGEV — Confidence-Gated Ensemble Verification

Scores an investigation's confidence (0-100) before allowing auto-remediation.
Breakdown:
  - Root cause clarity       (0–30 pts)
  - Supporting evidence      (0–30 pts)
  - Remediation reversibility(0–25 pts)
  - Blast radius containment (0–15 pts)

Only proceeds to auto-remediation when score >= CONFIDENCE_THRESHOLD.
"""

import json
import logging
from typing import List

import anthropic

from config import settings

logger = logging.getLogger(__name__)

_anthropic_client = None


def get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


async def calculate_confidence(
    root_cause_hypothesis: str,
    supporting_evidence: List[str],
    remediation_action: str,
    blast_radius: str,
) -> dict:
    """
    Use Claude to score the confidence of an investigation result.
    Returns {"score": int, "reasoning": str}
    """
    evidence_text = "\n".join(f"- {e}" for e in supporting_evidence)

    prompt = f"""You are a senior SRE evaluating the confidence of an automated incident investigation.
Score the following investigation from 0 to 100 using this rubric:

RUBRIC:
1. Root cause clarity (0-30 points):
   - 25-30: Very specific, pinpoints exact line/function/commit
   - 15-24: Clear general cause identified
   - 5-14: Vague but plausible hypothesis
   - 0-4: Unknown or speculative

2. Supporting evidence (0-30 points):
   - 25-30: Multiple corroborating data points (logs + commit + metrics)
   - 15-24: At least two corroborating sources
   - 5-14: Single data source
   - 0-4: No concrete evidence

3. Remediation reversibility (0-25 points):
   - 20-25: Fully reversible (revert PR, pod restart — no data loss risk)
   - 10-19: Mostly reversible (scale up, rollback)
   - 5-9: Partially reversible (config change)
   - 0-4: Irreversible or destructive

4. Blast radius containment (0-15 points):
   - 12-15: Single pod/service affected
   - 7-11: Multiple services but isolated
   - 3-6: Cross-service, some user impact
   - 0-2: Platform-wide or data integrity risk

INVESTIGATION TO SCORE:
Root cause hypothesis: {root_cause_hypothesis}

Supporting evidence:
{evidence_text}

Proposed remediation: {remediation_action}

Blast radius assessment: {blast_radius}

Respond with ONLY valid JSON in this exact format:
{{"score": <integer 0-100>, "reasoning": "<one paragraph explaining the score>"}}"""

    try:
        client = get_anthropic_client()
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        score = max(0, min(100, int(result.get("score", 50))))
        reasoning = result.get("reasoning", "")
        logger.info(f"CGEV score: {score}/100")
        return {"score": score, "reasoning": reasoning}
    except Exception as e:
        logger.error(f"Confidence calculation failed: {e}")
        # Conservative fallback — don't auto-remediate if we can't score
        return {"score": 40, "reasoning": f"Scoring unavailable: {e}"}
