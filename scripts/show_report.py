"""Show the complete daily report."""

from emailtools.database import get_session
from emailtools.reporter.generator import generate_report_data
from emailtools.reporter.email_sender import preview_report


def main():
    """Generate and display the report."""
    with get_session() as session:
        # Generate report data
        report_data = generate_report_data(session)

        # Render plain text report
        report_text = preview_report(report_data)

        # Display report
        print(report_text)


if __name__ == "__main__":
    main()
