# INtelliBOX

An automated email action tracking system for fast-paced software teams.

## Overview

INtelliBOX helps teams manage incoming Requests for Information (RFIs), data calls, and stakeholder requests by:
- Parsing emails using AI to extract actionable items
- Storing them in a database with metadata
- Generating nightly reports showing unassigned actions
- Tracking assignments and removing them from future reports

## Features (MVP)

✅ **Local .eml File Processing** - Drop email files in `data/inbox/` for automatic parsing
✅ **AI-Powered Action Extraction** - GPT-4 identifies action items, priorities, and due dates
✅ **SQLite Database** - Stores emails, actions, assignments, and processing logs
✅ **Nightly Email Reports** - Automated summaries sent to team distribution list
✅ **7-Day Program News** - AI-generated summary of recent activity

## Installation

### Requirements
- Python 3.11 or higher
- OpenAI API key

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd INtelliBOX
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and SMTP settings
   ```

5. **Initialize database**
   ```bash
   intellibox init
   ```

## Usage

### Process Emails

Drop `.eml` files in the `data/inbox/` directory and run:
```bash
intellibox process
```

### View Actions

```bash
# List all actions
intellibox actions list

# List unassigned actions only
intellibox actions list --unassigned
```

### Generate Reports

```bash
# Preview report without sending
intellibox report generate

# Send report immediately
intellibox report send

# Start scheduler for nightly reports (6:00 AM)
intellibox report schedule
```

### Database Commands

```bash
# View database contents
intellibox db show

# View specific table
intellibox db show --table actions
```

## Project Structure

```
INtelliBOX/
├── src/intellibox/          # Main application code
│   ├── ingestion/          # Email parsing and file watching
│   ├── ai/                 # GPT-4 integration
│   ├── reporter/           # Report generation and sending
│   └── utils/              # Shared utilities
├── tests/                  # Test suite
├── data/                   # Local data (gitignored)
│   ├── inbox/             # Drop .eml files here
│   ├── emails/            # Archived emails
│   └── intellibox.db      # SQLite database
└── alembic/               # Database migrations
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html
```

## Configuration

All configuration is managed via environment variables in `.env`:

- `OPENAI_API_KEY` - Your OpenAI API key
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` - Email sending configuration
- `REPORT_RECIPIENTS` - Comma-separated list of email addresses for nightly reports
- `PROGRAM_NEWS_DAYS` - Number of days to include in program news summary (default: 7)

## Roadmap

### MVP (Current)
- ✅ Local .eml file processing
- ✅ AI action extraction
- ✅ Nightly email reports

### Future Phases
- **Phase 4**: Web dashboard for action management
- **Phase 5**: Assignment handling via web UI and email replies
- **Phase 6**: IMAP integration for live email monitoring
- **Phase 7**: AWS deployment with RDS, Lambda, and SES

## Cost Estimation

**MVP Usage** (50-100 emails/day):
- OpenAI API: ~$5-15/month
- Total: <$20/month

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
