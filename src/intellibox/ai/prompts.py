"""Prompt templates for AI-powered email analysis."""

SYSTEM_PROMPT = """You are an expert email analyzer for a fast-paced software team. Your job is to identify actionable items from emails.

An "action item" is any task, request, or deliverable that requires team response. This includes:
- RFIs (Requests for Information)
- Data calls or reports
- Deliverables with deadlines
- Questions requiring responses
- Tasks assigned to the team
- Meeting action items

NOT action items:
- Pure FYI notices with no response needed
- System notifications
- Calendar invites (unless they request preparation)
- Thank you messages
"""

ACTION_EXTRACTION_PROMPT = """Analyze the following email and extract ALL action items that require team response.

Email Details:
Subject: {subject}
From: {from_name} <{from_address}>
Date: {date}
Body:
{body}

For each action item, extract:
1. **title**: Short, imperative description (e.g., "Submit Q1 security audit report")
2. **description**: Detailed context (1-2 sentences)
3. **priority**: "high", "medium", or "low" based on:
   - High: Urgent, executive visibility, hard deadline < 3 days
   - Medium: Important, deadline 3-7 days
   - Low: No urgency, deadline > 7 days or flexible
4. **due_date**: Extract from text (e.g., "by Friday" → actual date), null if not mentioned
5. **category**: Classify using one of the defined categories:
{categories}
6. **confidence**: Your confidence (0.0-1.0) that this is truly an action item

Respond ONLY with valid JSON in this exact format:
{{
  "actions": [
    {{
      "title": "Action title",
      "description": "Detailed description",
      "priority": "high|medium|low",
      "due_date": "YYYY-MM-DD" or null,
      "category": "category_name",
      "confidence": 0.95
    }}
  ]
}}

If there are NO action items, respond with:
{{
  "actions": []
}}

Current date for reference: {current_date}

JSON response:"""

PROGRAM_NEWS_PROMPT = """Analyze the following emails from the past {days} days and create a concise program news summary.

Focus on:
- Key themes and topics
- Important stakeholder communications
- Recurring issues or requests
- Overall program health indicators

Emails to summarize:
{email_summaries}

Create a 2-3 paragraph summary that a team lead can read in 30 seconds during morning scrum.

Summary:"""

STRUCTURED_PROGRAM_NEWS_PROMPT = """Analyze the following emails from the past {days} days and generate a structured program news summary.

## Email Activity Summary
Total emails: {email_count}
Date range: Past {days} days

## Emails to analyze:
{email_summaries}

## Generate Structured Output

Provide a JSON response with the following structure:

{{
  "critical_updates": [
    "Brief critical item 1 (if any)",
    "Brief critical item 2 (if any)"
  ],
  "trending_topics": [
    {{
      "topic": "Topic name",
      "count": number,
      "trend": "up|down|stable",
      "description": "One sentence about this topic"
    }}
  ],
  "volume_summary": {{
    "total_emails": {email_count},
    "trend_description": "Brief comparison to typical volume (e.g., '20% above average')",
    "notable_pattern": "Any notable pattern in timing or volume"
  }},
  "top_senders": [
    {{
      "sender": "email@example.com or name",
      "count": number,
      "context": "Brief note about their emails"
    }}
  ],
  "key_takeaways": [
    "Most important takeaway 1",
    "Most important takeaway 2",
    "Most important takeaway 3"
  ]
}}

Focus on being concise and actionable. If a section has no relevant data, use empty arrays or appropriate defaults.
Critical updates should only include truly urgent items requiring immediate attention.
Trending topics should identify the 2-3 most common themes.
Top senders should list the 3-4 most active senders.

JSON response:"""

REPORT_INSIGHTS_PROMPT = """You are generating a program intelligence briefing for a director. Cross-reference the action items below against the Program Knowledge Base documents provided in your system instructions.

## Current Action Pipeline

{action_details}

## Pipeline Metrics

- Total actions: {total_actions}
- Awaiting assignment: {unassigned_count} (High: {high_priority_count}, Medium: {medium_priority_count}, Low: {low_priority_count})
- In progress: {assigned_in_progress}
- Completed: {completed_count}
- Overdue: {overdue_count}
- Due this week: {due_this_week_count}

## Recent Email Traffic ({days} days)

{email_summaries}

## Analysis Instructions

Cross-reference the actions and emails against the Program Knowledge Base documents. Generate analysis in these four areas:

1. **SOW Alignment** — Map actions to deliverables, CLINs, or milestones from program documents. Flag actions that don't match any documented scope (potential scope creep) and documented deliverables with no matching actions (coverage gaps).

2. **Risk Radar** — Identify risks by cross-referencing actions against known issues, deadlines, or concerns from program documents. Include severity and suggested mitigation.

3. **Process Compliance** — Compare workflow patterns (triage speed, assignment rates, priority distribution) against documented team processes and procedures.

4. **Trend Intelligence** — Connect action patterns to program context. What do the current actions tell us about program trajectory?

Be specific and factual. Use exact numbers from the metrics above. Name the specific program document that informed each finding.

Respond with this JSON:

{{
  "executive_summary": {{
    "headline": "Short, punchy status line — max 12 words. Lead with the most critical number or finding. Example: '4 of 5 SOW deliverables at risk — 27 actions unassigned'",
    "key_finding": "One sentence: the most important insight from cross-referencing actions against program documents. Name the specific document.",
    "top_risk": "One sentence: the single biggest risk right now, with evidence.",
    "recommended_action": "One sentence: the single most important thing the director should do today."
  }},
  "sow_alignment": {{
    "mapped_deliverables": [
      {{
        "deliverable": "SOW deliverable or CLIN name",
        "related_actions": ["action title 1", "action title 2"],
        "status": "on_track|at_risk|behind",
        "note": "Brief observation about this deliverable's status"
      }}
    ],
    "unmapped_actions": [
      {{
        "action_title": "Action that doesn't map to any SOW item",
        "concern": "Why this might be scope creep or a missing SOW line item"
      }}
    ],
    "coverage_gaps": ["SOW deliverable with no matching actions in the pipeline"]
  }},
  "risk_radar": [
    {{
      "risk": "Specific risk description",
      "severity": "high|medium|low",
      "evidence": "What actions or patterns indicate this risk",
      "mitigation": "Suggested next step"
    }}
  ],
  "process_compliance": {{
    "observations": [
      {{
        "area": "Process area (e.g., Triage, Escalation, Assignment, Response Time)",
        "finding": "What the data shows vs what the process docs prescribe",
        "recommendation": "What to adjust"
      }}
    ],
    "overall_health": "green|yellow|red"
  }},
  "trend_intelligence": {{
    "patterns": [
      {{
        "pattern": "Description of the trend",
        "context": "How it relates to program documents",
        "impact": "What this means for the team"
      }}
    ],
    "workload_forecast": "Forward-looking statement about expected workload based on program documents and current action patterns"
  }},
  "recommendations": [
    "Specific, actionable recommendation grounded in program documents",
    "Another recommendation"
  ]
}}

If no Program Knowledge Base is loaded, provide general analysis based on action content and email patterns.

JSON response:"""
