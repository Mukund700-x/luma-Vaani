"""
Integration test — Hospital creation and department CRUD.

Requires a running test database.
Run with: pytest tests/integration/test_hospitals.py -v
"""

import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestHospitalAPI:
    """Integration tests for the hospital management endpoints."""

    async def test_create_hospital_requires_super_admin(self, client, auth_headers):
        """HOSPITAL_ADMIN cannot create a new hospital."""
        response = await client.post(
            "/api/v1/hospitals",
            json={
                "name": "New Hospital",
                "slug": "new-hospital",
                "contact_email": "new@hospital.example",
                "contact_phone": "+91-9000001234",
                "address": "Test Address",
            },
            headers=auth_headers,
        )
        # HOSPITAL_ADMIN should get 403
        assert response.status_code in (403, 401)

    async def test_list_departments_returns_hospital_scoped(
        self, client, auth_headers, test_hospital, db
    ):
        """Departments list is scoped to the requesting hospital."""
        from app.modules.departments.models import Department

        # Create a department for the test hospital
        dept = Department(
            hospital_id=test_hospital.id,
            name="Cardiology",
            slug="cardiology-test",
            is_active=True,
        )
        db.add(dept)
        await db.flush()

        response = await client.get(
            f"/api/v1/hospitals/{test_hospital.id}/departments",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        dept_ids = [d["id"] for d in data["items"]]
        assert str(dept.id) in dept_ids


@pytest.mark.asyncio
class TestNotificationTemplateAPI:
    """Integration tests for notification template CRUD."""

    async def test_list_templates_empty_for_new_hospital(
        self, client, auth_headers, test_hospital
    ):
        response = await client.get(
            f"/api/v1/hospitals/{test_hospital.id}/notification-templates",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_template(self, client, auth_headers, test_hospital):
        response = await client.post(
            f"/api/v1/hospitals/{test_hospital.id}/notification-templates",
            json={
                "event_type": "appointment.confirmed",
                "channel": "SMS",
                "language": "en",
                "body": "Hi {{ patient_name }}, your appointment is confirmed. Ref: {{ appointment_ref }}.",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["event_type"] == "appointment.confirmed"
        assert data["channel"] == "SMS"
        assert "{{ patient_name }}" in data["body"]

    async def test_seed_default_templates(self, client, auth_headers, test_hospital):
        response = await client.post(
            f"/api/v1/hospitals/{test_hospital.id}/notification-templates/seed",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "created" in data
        assert data["created"] > 0


@pytest.mark.asyncio
class TestKnowledgeAPI:
    """Integration tests for the Knowledge Base (RAG) API."""

    async def test_create_document(self, client, auth_headers, test_hospital):
        response = await client.post(
            f"/api/v1/hospitals/{test_hospital.id}/knowledge/documents",
            json={
                "title": "Test FAQ",
                "source_type": "FAQ",
                "access_scope": "PUBLIC",
                "content": "Q: What are visiting hours? A: 10am to 12pm daily.",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test FAQ"
        assert data["source_type"] == "FAQ"
        assert data["access_scope"] == "PUBLIC"
        # embedding_status will be FAILED (no API key in test) or PENDING
        assert data["embedding_status"] in ("PENDING", "FAILED", "INDEXED")

    async def test_list_documents(self, client, auth_headers, test_hospital, db):
        from app.modules.knowledge.models import KnowledgeDocument
        doc = KnowledgeDocument(
            hospital_id=test_hospital.id,
            title="Visiting Hours",
            source_type="VISITING_HOURS",
            access_scope="PUBLIC",
            content="10am to 12pm.",
            language="en",
            is_active=True,
            embedding_status="PENDING",
            metadata={},
        )
        db.add(doc)
        await db.flush()

        response = await client.get(
            f"/api/v1/hospitals/{test_hospital.id}/knowledge/documents",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_cross_hospital_document_isolation(
        self, client, auth_headers, test_hospital, db
    ):
        """Documents from other hospitals must never appear in search results."""
        from app.modules.hospitals.models import Hospital
        from app.modules.knowledge.models import KnowledgeDocument

        # Create another hospital
        other_hospital = Hospital(
            name="Other Hospital",
            slug="other-hospital-isolation-test",
            contact_email="other@hospital.example",
            contact_phone="+91-9000001111",
            address="Other Street",
            config={},
            is_active=True,
        )
        db.add(other_hospital)
        await db.flush()

        # Create a document for the other hospital
        other_doc = KnowledgeDocument(
            hospital_id=other_hospital.id,
            title="Secret Policy of Other Hospital",
            source_type="POLICY",
            access_scope="PUBLIC",
            content="This should never be visible to Test Hospital.",
            language="en",
            is_active=True,
            embedding_status="PENDING",
            metadata={},
        )
        db.add(other_doc)
        await db.flush()

        # Test hospital should not see other hospital's documents
        response = await client.get(
            f"/api/v1/hospitals/{test_hospital.id}/knowledge/documents",
            headers=auth_headers,
        )
        assert response.status_code == 200
        doc_ids = [d["id"] for d in response.json()["items"]]
        assert str(other_doc.id) not in doc_ids, (
            "CRITICAL: Cross-hospital document isolation failed!"
        )
