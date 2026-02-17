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

REPORT_INSIGHTS_PROMPT = """You are generating an executive briefing for a program director reviewing their team's action item pipeline.

## Program Status

Total action items across the program: {total_actions}
- Awaiting assignment: {unassigned_count} (High: {high_priority_count}, Medium: {medium_priority_count}, Low: {low_priority_count})
- Assigned and in progress: {assigned_in_progress}
- Completed: {completed_count}
- Overdue (not yet completed): {overdue_count}
- Due this week: {due_this_week_count}

Unassigned actions by category:
{category_breakdown}

Recent inbound email traffic ({days} days):
{email_summaries}

## Instructions

Write for a director who has 60 seconds to understand:
1. What is the overall health of our action pipeline?
2. What external requests are driving the most work?
3. What needs their attention right now?

Be specific and factual — use the exact numbers provided above. Do not contradict the data. If overdue count is {overdue_count}, state that number exactly. Do not use filler language like "well-managed" unless the data supports it.

Respond with this JSON structure:

{{
  "executive_summary": "2-3 sentences. Lead with the most important fact. State exact numbers (e.g., '{overdue_count} overdue items' if overdue > 0, '{unassigned_count} items awaiting assignment'). Then identify the top risk or bottleneck. End with one concrete recommendation.",
  "trends": {{
    "action_volume": "What does the volume of incoming requests suggest? Are certain senders or topics driving most of the workload?",
    "priority_distribution": "Is the mix of high/medium/low appropriate, or is there a skew that suggests triage issues?",
    "response_patterns": "Based on the ratio of unassigned vs. in-progress vs. completed, how is throughput?"
  }},
  "category_insights": [
    {{
      "category": "category_name",
      "count": number,
      "insight": "One-sentence observation relevant to a director",
      "urgency": "high|medium|low"
    }}
  ],
  "urgent_items": [
    {{
      "action_title": "title of a specific action that needs attention",
      "reason": "Why — be specific (overdue, high priority unassigned, etc.)",
      "recommended_action": "One concrete next step"
    }}
  ],
  "bottlenecks": "Where is work getting stuck? Look at the unassigned-to-completed ratio and any category patterns.",
  "recommendations": [
    "Specific, actionable recommendation grounded in the data above",
    "Another recommendation"
  ]
}}

JSON response:"""
