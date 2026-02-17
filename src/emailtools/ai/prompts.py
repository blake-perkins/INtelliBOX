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
5. **category**: Classify as "RFI", "data_call", "stakeholder_request", "meeting_action", "deliverable", or "other"
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

REPORT_INSIGHTS_PROMPT = """Analyze the following action items and recent email activity to generate actionable insights.

## Current Action Items ({total_actions} total)
Priority breakdown:
- High priority: {high_priority_count}
- Medium priority: {medium_priority_count}
- Low priority: {low_priority_count}

Overdue actions: {overdue_count}
Due this week: {due_this_week_count}

Actions by category:
{category_breakdown}

Recent email activity ({days} days):
{email_summaries}

## Generate Structured Insights

Provide a JSON response with the following structure:

{{
  "executive_summary": "2-3 sentence overview of current workload and key priorities",
  "trends": {{
    "action_volume": "Are actions increasing or decreasing? Any patterns?",
    "priority_distribution": "Is the high-priority ratio concerning or healthy?",
    "response_patterns": "How quickly are actions being addressed?"
  }},
  "category_insights": [
    {{
      "category": "category_name",
      "count": number,
      "insight": "Key observation about this category",
      "urgency": "high|medium|low"
    }}
  ],
  "urgent_items": [
    {{
      "action_title": "title",
      "reason": "Why this needs immediate attention",
      "recommended_action": "Specific next step"
    }}
  ],
  "bottlenecks": "Identify any patterns of delayed responses or recurring request types",
  "recommendations": [
    "Specific actionable recommendation 1",
    "Specific actionable recommendation 2",
    "Specific actionable recommendation 3"
  ]
}}

Focus on actionable insights that help the team prioritize and respond effectively.

JSON response:"""
