def get_knowledge_documents_for_app(app_id):
    """
    Final service interface for retrieving document metadata.

    Later this should query Supabase tables such as:
    - documents
    - knowledge_documents

    and return file metadata + storage paths.

    For now, it returns placeholder structured data.
    """

    return [
        {
            "document_id": "doc-001",
            "application_id": app_id,
            "title": "HMS Overview",
            "document_type": "txt",
            "category": "application",
            "storage_path": f"applications/{app_id}/documents/hms_overview.txt",
            "is_active": True,
        },
        {
            "document_id": "doc-002",
            "application_id": app_id,
            "title": "Node Performance Best Practices",
            "document_type": "txt",
            "category": "common",
            "storage_path": "common/node_performance.txt",
            "is_active": True,
        },
    ]


def get_document_content(document_record):
    """
    Final service interface for fetching document content.

    Later this should:
    - read from Supabase Storage
    - fetch by storage_path
    - return extracted text

    For now, returns placeholder text based on document title.
    """

    title = document_record["title"]

    if title == "HMS Overview":
        return (
            "Hospital Management System handles patient records, appointments, "
            "billing, clinical workflows, and reporting. Common modules include "
            "patient management, appointment scheduling, staff management, and analytics."
        )

    if title == "Node Performance Best Practices":
        return (
            "Node.js performance issues often involve event loop blocking, "
            "inefficient database access, missing indexes, and high container CPU usage."
        )

    return ""