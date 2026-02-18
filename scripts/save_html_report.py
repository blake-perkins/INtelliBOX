"""Save HTML report to file for viewing."""

from pathlib import Path
from intellibox.database import get_session
from intellibox.reporter.generator import generate_report_data
from intellibox.reporter.email_sender import render_template


def main():
    """Generate and save HTML report."""
    with get_session() as session:
        # Generate report data
        report_data = generate_report_data(session)

        # Render HTML report
        html_content = render_template("daily_report.html", report_data)

        # Save to file
        output_file = Path("data/sample_report.html")
        output_file.write_text(html_content, encoding='utf-8')

        print(f"[OK] HTML report saved to: {output_file}")
        print(f"\nOpen this file in your browser to see the formatted report!")


if __name__ == "__main__":
    main()
