"""Step definitions for Knowledge Base BDD scenarios."""

from behave import given, when, then, use_step_matcher
from features.environment import seed, make_session


@given('a knowledge document "{filename}" exists')
def step_kb_doc_exists(context, filename):
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "txt"
    seed(context, "knowledge_document",
         filename=filename,
         file_type=ext,
         file_size=100,
         extracted_text=f"Content of {filename}",
         extraction_status="success")


@given('a knowledge document "{filename}" exists with description "{desc}"')
def step_kb_doc_exists_with_desc(context, filename, desc):
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "txt"
    seed(context, "knowledge_document",
         filename=filename,
         file_type=ext,
         file_size=100,
         extracted_text=f"Content of {filename}",
         extraction_status="success",
         description=desc)


# Use regex matcher for upload steps to avoid ambiguous parse patterns
use_step_matcher("re")


@when(r'I upload a TXT file "(?P<filename>[^"]+)" with content "(?P<content>[^"]+)" described as "(?P<desc>[^"]+)"')
def step_upload_txt_with_desc(context, filename, content, desc):
    context.response = context.client.post(
        "/knowledge-base/upload",
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
        data={"description": desc},
        follow_redirects=False,
    )


@when(r'I upload a TXT file "(?P<filename>[^"]+)" with content "(?P<content>[^"]+)"')
def step_upload_txt(context, filename, content):
    context.response = context.client.post(
        "/knowledge-base/upload",
        files={"file": (filename, content.encode("utf-8"), "text/plain")},
        data={"description": ""},
        follow_redirects=False,
    )


use_step_matcher("parse")


@when('I upload an unsupported file "{filename}" to the knowledge base')
def step_upload_unsupported(context, filename):
    context.response = context.client.post(
        "/knowledge-base/upload",
        files={"file": (filename, b"bad content", "application/octet-stream")},
        data={"description": ""},
        follow_redirects=False,
    )


@when('I delete knowledge document {doc_id:d}')
def step_delete_kb_doc(context, doc_id):
    context.response = context.client.post(
        f"/knowledge-base/{doc_id}/delete",
        follow_redirects=False,
    )


@then('the response redirects')
def step_response_redirects(context):
    assert context.response.status_code in (301, 302, 303, 307, 308), \
        f"Expected redirect, got {context.response.status_code}"


@then('the knowledge base has {count:d} document')
def step_kb_has_count_singular(context, count):
    from emailtools.models import KnowledgeDocument
    session = make_session(context)
    actual = session.query(KnowledgeDocument).count()
    session.close()
    assert actual == count, f"Expected {count} documents, got {actual}"


@then('the knowledge base has {count:d} documents')
def step_kb_has_count_plural(context, count):
    from emailtools.models import KnowledgeDocument
    session = make_session(context)
    actual = session.query(KnowledgeDocument).count()
    session.close()
    assert actual == count, f"Expected {count} documents, got {actual}"
