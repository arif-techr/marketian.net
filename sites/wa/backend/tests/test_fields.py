"""Dynamic messages: extra columns imported from Excel/CSV, used as {score} etc. in messages."""
import csv
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.broadcasts import runner
from apps.broadcasts.models import Campaign, CampaignTarget
from apps.contacts.models import Contact, ContactField
from apps.contacts.tabular import field_key
from tests.helpers import me

pytestmark = pytest.mark.django_db


def xlsx(rows, name="students.xlsx"):
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(name, buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


SHEET = [
    ["Student Name", "Mobile", "Score", "City", "Notes"],
    ["Rahim", 8801712345678, 85, "Bogura", "x"],   # Excel keeps numbers as numbers
    ["Karim", "01812345678", 72.5, "", "y"],
]


# ---------- placeholders ----------

@pytest.mark.parametrize("message,expected", [
    ("Hi {name}, your score is {score}.", "Hi Rahim, your score is 85."),
    ("City: {city|unknown}", "City: unknown"),            # known field, empty for this contact -> fallback
    ("Due {due}", "Due "),                                # known field, no value, no fallback
    ("Call {phone}", "Call +8801712345678"),
    ("Code {abc} and {x y} stay", "Code {abc} and {x y} stay"),  # not placeholders: left alone
    ("{SCORE} {Name}", "85 Rahim"),
    ("ফল: {নাম্বার}", "ফল: ৯০"),
])
def test_personalize_fields(message, expected):
    out = runner.personalize(message, "Rahim", {"score": "85", "city": "", "নাম্বার": "৯০"}, known={"score", "city", "due"},
                             phone="8801712345678")
    assert out == expected


def test_personalize_name_rules_unchanged():
    assert runner.personalize("Hi {name}, {NAME|x}", "Ana") == "Hi Ana, Ana"
    assert runner.personalize("Hi {name|friend}!", "") == "Hi friend!"


@pytest.mark.parametrize("label,key", [("Exam Score", "exam_score"), (" Due-Amount (Tk) ", "due_amount_tk"), ("নাম্বার", "নাম্বার"), ("!!!", "field")])
def test_field_key(label, key):
    assert field_key(label) == key


# ---------- import ----------

def test_preview_xlsx_guesses_columns(client):
    r = client.post("/api/contacts/import/preview/", {"file": xlsx(SHEET)}, format="multipart").json()
    assert r["has_header"] is True
    assert r["headers"] == ["Student Name", "Mobile", "Score", "City", "Notes"]
    assert r["columns"] == ["name", "phone", "ignore", "ignore", "ignore"]
    assert r["sample"][0][:3] == ["Rahim", "8801712345678", "85"] and r["total_rows"] == 2


def test_preview_suggests_fields_you_already_use(client):
    ContactField.objects.create(owner=me(), key="score", label="Score")
    r = client.post("/api/contacts/import/preview/", {"file": xlsx(SHEET)}, format="multipart").json()
    assert r["columns"][2] == "field"


def test_import_xlsx_with_chosen_columns(client):
    cols = '["name","phone","field","field","ignore"]'
    r = client.post("/api/contacts/import/", {"file": xlsx(SHEET), "columns": cols, "new_list": "Class 9"}, format="multipart").json()
    assert r["created"] == 2 and r["fields"] == ["city", "score"]
    rahim = Contact.objects.get(phone="8801712345678")
    assert rahim.name == "Rahim" and rahim.fields == {"score": "85", "city": "Bogura"}
    assert Contact.objects.get(phone="8801812345678").fields == {"score": "72.5"}  # empty cells aren't stored
    assert sorted(ContactField.objects.filter(owner=me()).values_list("key", "label")) == [("city", "City"), ("score", "Score")]


def test_upload_like_the_import_screen_sends_it(client):
    """Multipart form: every value is text, "no list" is an empty list_id."""
    r = client.post("/api/contacts/import/", {"file": xlsx(SHEET), "columns": '["name","phone","field","ignore","ignore"]',
                                              "has_header": "true", "list_id": "", "new_list": ""}, format="multipart")
    assert r.status_code == 200, r.json()
    assert r.json()["created"] == 2 and r.json()["list"] is None


def test_reimport_updates_values_and_keeps_other_columns(client):
    client.post("/api/contacts/import/", {"file": xlsx(SHEET), "columns": '["name","phone","field","field","ignore"]'}, format="multipart")
    r = client.post("/api/contacts/import/", {"text": "Mobile,Score\n01712345678,91", "columns": ["phone", "field"]}, format="json").json()
    assert r["updated"] == 0 and r["fields_updated"] == 1
    assert Contact.objects.get(phone="8801712345678").fields == {"score": "91", "city": "Bogura"}


def test_import_needs_a_phone_column(client):
    r = client.post("/api/contacts/import/", {"file": xlsx(SHEET), "columns": '["name","ignore","field","ignore","ignore"]'}, format="multipart")
    assert r.status_code == 400 and "columns" in r.json()["fields"]


def test_pasted_text_without_columns_still_works(client):
    r = client.post("/api/contacts/import/", {"text": "Rahim, 01712345678"}, format="json").json()
    assert r["created"] == 1 and r["fields"] == []


@pytest.mark.parametrize("name,data,msg", [
    ("old.xls", b"\xd0\xcf\x11\xe0", ".xls"),
    ("fake.xlsx", b"PK not really a zip", "Excel"),
])
def test_bad_spreadsheets_are_explained(client, name, data, msg):
    r = client.post("/api/contacts/import/preview/", {"file": SimpleUploadedFile(name, data)}, format="multipart")
    assert r.status_code == 400 and msg in r.json()["error"]


def test_csv_file_upload_in_windows_encoding(client):
    data = "Name;Phone;Score\nJosé;01712345678;99\n".encode("cp1252")
    r = client.post("/api/contacts/import/", {"file": SimpleUploadedFile("list.csv", data), "columns": '["name","phone","field"]'},
                    format="multipart").json()
    assert r["created"] == 1
    c = Contact.objects.get()
    assert c.name == "José" and c.fields == {"score": "99"}


# ---------- fields API ----------

def test_fields_api_and_isolation(client):
    r = client.post("/api/contact-fields/", {"label": "Due Amount"}, format="json")
    assert r.status_code == 201 and r.json()["key"] == "due_amount"
    assert client.post("/api/contact-fields/", {"label": "due amount"}, format="json").status_code == 400
    assert client.post("/api/contact-fields/", {"label": "Name"}, format="json").status_code == 400  # built in
    assert [f["key"] for f in client.get("/api/contact-fields/").json()] == ["due_amount"]

    bob = get_user_model().objects.create_user("bob", password="a-long-test-password")
    other = APIClient()
    other.force_authenticate(bob)
    assert other.get("/api/contact-fields/").json() == []
    assert other.delete(f"/api/contact-fields/{r.json()['id']}/").status_code == 404
    assert client.delete(f"/api/contact-fields/{r.json()['id']}/").status_code == 204


def test_contact_serializer_shows_fields(client):
    Contact.objects.create(owner=me(), phone="8801712345678", fields={"score": "85"})
    assert client.get("/api/contacts/").json()["results"][0]["fields"] == {"score": "85"}


def test_export_includes_field_columns(client):
    ContactField.objects.create(owner=me(), key="score", label="Score")
    Contact.objects.create(owner=me(), phone="8801712345678", name="Rahim", fields={"score": "85"})
    rows = list(csv.reader(io.StringIO(client.get("/api/contacts/export/").content.decode("utf-8-sig"))))
    assert rows[0][-1] == "Score" and rows[1][-1] == "85"


# ---------- sending ----------

def test_runner_sends_each_person_their_own_values(provider, account):
    ContactField.objects.create(owner=me(), key="score", label="Score")
    a = Contact.objects.create(owner=me(), phone="8801700000001", name="Rahim", fields={"score": "85"})
    b = Contact.objects.create(owner=me(), phone="8801700000002", name="Karim", fields={})
    c = Campaign.objects.create(owner=me(), message="{name}: {score|absent} {other}", delay_min_seconds=0, delay_max_seconds=0,
                                batch_size=0, status="running")
    c.sender_accounts.add(account)
    for i, ct in enumerate([a, b]):
        CampaignTarget.objects.create(campaign=c, contact=ct, recipient_jid=f"{ct.phone}@s.whatsapp.net", recipient_name=ct.name,
                                      position=i, account_label="")
    runner.run_campaign(c.pk)
    assert [t for _, _, t, _ in provider.sent] == ["Rahim: 85 {other}", "Karim: absent {other}"]
