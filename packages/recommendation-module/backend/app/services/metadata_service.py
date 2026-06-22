from app.shared.mock_data import MOCK_APPLICATIONS


def get_application_metadata(app_id: str) -> dict:
    app = MOCK_APPLICATIONS.get(app_id)

    if not app:
        raise ValueError(f"Application '{app_id}' not found in mock data")

    return app