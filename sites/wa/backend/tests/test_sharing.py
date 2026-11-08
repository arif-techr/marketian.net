"""Sharing WhatsApp accounts, contact lists and templates between workspaces with a one-time code."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.broadcasts import runner
from apps.broadcasts.models import Campaign, CampaignTarget, MessageTemplate
from apps.contacts.models import Contact, ContactField, ContactList
from apps.core.models import TeamMember
from apps.sharing.models import Share, ShareInvite
from apps.whatsapp.models import WhatsAppAccount

pytestmark = pytest.mark.django_db
User = get_user_model()
PW = "a-long-test-password"


def signed_in(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def alice(db):
    return User.objects.create_user("alice", password=PW)


@pytest.fixture
def bob(db):
    return User.objects.create_user("bob", password=PW)


@pytest.fixture
def stuff(alice):
    acc = WhatsAppAccount.objects.create(owner=alice, label="Shop phone", provider="fake", status="connected", phone="8801000000001")
    lst = ContactList.objects.create(owner=alice, name="VIP")
    for i in range(3):
        Contact.objects.create(owner=alice, phone=f"88017000000{i}", name=f"C{i}", fields={"score": str(80 + i)}).lists.add(lst)
    Contact.objects.create(owner=alice, phone="8801799999999", name="Private")  # not in the list
    ContactField.objects.create(owner=alice, key="score", label="Score")
    tpl = MessageTemplate.objects.create(owner=alice, title="Eid", body="Eid Mubarak {name}, score {score}")
    return {"account": acc, "list": lst, "template": tpl}


def invite(alice, stuff, username="bob", **kw):
    body = {"username": username, "account_ids": [stuff["account"].id], "list_ids": [stuff["list"].id],
            "template_ids": [stuff["template"].id], **kw}
    return signed_in(alice).post("/api/sharing/invites/", body, format="json")


@pytest.fixture
def shared(alice, bob, stuff):
    r = invite(alice, stuff).json()
    assert signed_in(bob).post(f"/api/sharing/invites/{r['id']}/accept/", {"code": r["code"]}, format="json").status_code == 200
    return stuff


# ---------- the invitation and its code ----------

def test_invite_shows_a_code_valid_for_ten_minutes(alice, bob, stuff):
    r = invite(alice, stuff)
    assert r.status_code == 201
    d = r.json()
    assert len(d["code"]) == 6 and d["code"].isdigit() and d["status"] == "pending"
    inv = ShareInvite.objects.get(pk=d["id"])
    assert timedelta(minutes=9) < inv.expires_at - timezone.now() <= timedelta(minutes=10)
    assert d["code"] not in inv.code_digest  # only a keyed hash is stored
    # The receiver sees the offer with its details, but never the code.
    received = signed_in(bob).get("/api/sharing/").json()["received_invites"]
    assert received[0]["from"] == "alice" and "code" not in received[0]
    assert received[0]["items"]["lists"] == [{"id": stuff["list"].id, "name": "VIP", "contact_count": 3}]
    assert signed_in(bob).get("/api/dashboard/").json()["share_invites"] == 1


@pytest.mark.parametrize("username,msg", [("nobody", "no user"), ("alice", "yourself")])
def test_invite_validation(alice, stuff, username, msg):
    r = invite(alice, stuff, username=username)
    assert r.status_code == 400 and msg in str(r.json()["fields"]["username"])


def test_invite_needs_own_items(alice, bob, stuff):
    other = WhatsAppAccount.objects.create(owner=bob, label="Bob", provider="fake", status="connected", phone="8801000000009")
    r = signed_in(alice).post("/api/sharing/invites/", {"username": "bob", "account_ids": [other.id]}, format="json")
    assert r.status_code == 400  # can't offer someone else's phone


def test_cannot_share_with_a_team_member(alice, bob, stuff):
    helper = User.objects.create_user("helper", password=PW)
    TeamMember.objects.create(user=helper, owner=bob)
    r = invite(alice, stuff, username="helper")
    assert r.status_code == 400 and "Share with bob" in str(r.json()["fields"]["username"])


def test_wrong_codes_then_locked(alice, bob, stuff):
    d = invite(alice, stuff).json()
    wrong = "000000" if d["code"] != "000000" else "111111"
    c = signed_in(bob)
    for left in (4, 3, 2, 1):
        r = c.post(f"/api/sharing/invites/{d['id']}/accept/", {"code": wrong}, format="json")
        assert r.status_code == 400 and f"{left} " in r.json()["error"]
    r = c.post(f"/api/sharing/invites/{d['id']}/accept/", {"code": wrong}, format="json")
    assert "too many" in r.json()["error"]
    assert c.post(f"/api/sharing/invites/{d['id']}/accept/", {"code": d["code"]}, format="json").status_code == 409
    assert not Share.objects.exists()
    # The sharer can issue a fresh code for the same offer.
    again = signed_in(alice).post(f"/api/sharing/invites/{d['id']}/new-code/").json()
    assert c.post(f"/api/sharing/invites/{d['id']}/accept/", {"code": again["code"]}, format="json").status_code == 200


def test_expired_code(alice, bob, stuff):
    d = invite(alice, stuff).json()
    ShareInvite.objects.filter(pk=d["id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
    r = signed_in(bob).post(f"/api/sharing/invites/{d['id']}/accept/", {"code": d["code"]}, format="json")
    assert r.status_code == 409 and "expired" in r.json()["error"]
    assert signed_in(bob).get("/api/sharing/").json()["received_invites"] == []
    assert signed_in(alice).get("/api/sharing/").json()["sent_invites"][0]["status"] == "expired"


def test_only_the_invited_user_can_accept(alice, bob, stuff):
    d = invite(alice, stuff).json()
    carol = User.objects.create_user("carol", password=PW)
    assert signed_in(carol).post(f"/api/sharing/invites/{d['id']}/accept/", {"code": d["code"]}, format="json").status_code == 404


def test_decline_and_cancel(alice, bob, stuff):
    d1 = invite(alice, stuff).json()
    assert signed_in(bob).post(f"/api/sharing/invites/{d1['id']}/decline/").status_code == 200
    d2 = invite(alice, stuff).json()
    assert signed_in(alice).post(f"/api/sharing/invites/{d2['id']}/cancel/").status_code == 200
    r = signed_in(bob).post(f"/api/sharing/invites/{d2['id']}/accept/", {"code": d2["code"]}, format="json")
    assert r.status_code == 409 and not Share.objects.exists()


def test_team_members_cannot_share_or_accept(alice, bob, stuff):
    helper = User.objects.create_user("helper", password=PW)
    TeamMember.objects.create(user=helper, owner=alice)
    assert signed_in(helper).post("/api/sharing/invites/", {"username": "bob", "template_ids": [stuff["template"].id]},
                                  format="json").status_code == 403
    assert signed_in(helper).get("/api/sharing/").status_code == 403


# ---------- what the receiver gets ----------

def test_receiver_sees_shared_items_flagged(bob, shared):
    c = signed_in(bob)
    acc = c.get("/api/accounts/").json()["results"]
    assert [(a["label"], a["shared_by"], a["qr"]) for a in acc] == [("Shop phone", "alice", None)]
    assert [(l["name"], l["shared_by"], l["contact_count"]) for l in c.get("/api/contact-lists/").json()] == [("VIP", "alice", 3)]
    assert [(t["title"], t["shared_by"]) for t in c.get("/api/templates/").json()] == [("Eid", "alice")]
    assert [(f["key"], f["shared_by"]) for f in c.get("/api/contact-fields/").json()] == [("score", "alice")]
    members = c.get(f"/api/contacts/?list={shared['list'].id}").json()["results"]
    assert len(members) == 3 and all(m["shared_by"] == "alice" for m in members)
    assert c.get("/api/contacts/").json()["count"] == 0  # alice's other contacts stay private
    assert c.get(f"/api/templates/{shared['template'].id}/").status_code == 200


def test_receivers_team_member_sees_them_too(bob, shared):
    helper = User.objects.create_user("helper", password=PW)
    TeamMember.objects.create(user=helper, owner=bob)
    assert len(signed_in(helper).get("/api/accounts/").json()["results"]) == 1


def test_shared_items_cannot_be_changed(bob, shared):
    c = signed_in(bob)
    acc, lst, tpl = shared["account"], shared["list"], shared["template"]
    member = Contact.objects.filter(lists=lst).first()
    assert c.patch(f"/api/accounts/{acc.id}/", {"label": "mine"}, format="json").status_code == 404
    assert c.delete(f"/api/accounts/{acc.id}/").status_code == 404
    assert c.post(f"/api/accounts/{acc.id}/relink/").status_code == 404
    assert c.delete(f"/api/contact-lists/{lst.id}/").status_code == 404
    assert c.patch(f"/api/templates/{tpl.id}/", {"title": "x"}, format="json").status_code == 404
    assert c.patch(f"/api/contacts/{member.id}/", {"name": "x"}, format="json").status_code == 404
    c.post("/api/contacts/bulk/", {"action": "opt_out", "ids": [member.id]}, format="json")
    member.refresh_from_db()
    assert not member.opted_out


def test_receiver_sends_with_shared_phone_list_and_template(provider, bob, shared):
    r = signed_in(bob).post("/api/campaigns/", {
        "message": shared["template"].body, "sender_account_ids": [shared["account"].id],
        "contact_list_ids": [shared["list"].id], "delay_min_seconds": 3, "delay_max_seconds": 3, "batch_size": 0,
    }, format="json")
    assert r.status_code == 201, r.json()
    camp = Campaign.objects.get(pk=r.json()["id"])
    assert camp.owner == bob and camp.targets.count() == 3
    Campaign.objects.filter(pk=camp.pk).update(status="running", delay_min_seconds=0, delay_max_seconds=0)
    runner.run_campaign(camp.pk)
    texts = sorted(t for _, _, t, _ in provider.sent)
    assert texts == ["Eid Mubarak C0, score 80", "Eid Mubarak C1, score 81", "Eid Mubarak C2, score 82"]
    assert {sid for sid, *_ in provider.sent} == {shared["account"].session_id}


def test_a_shared_phone_never_runs_two_campaigns_at_once(alice, bob, shared):
    a = Campaign.objects.create(owner=alice, message="a")
    a.sender_accounts.add(shared["account"])
    b = Campaign.objects.create(owner=bob, message="b")
    b.sender_accounts.add(shared["account"])
    assert runner.claim_next().pk == a.pk
    assert runner.claim_next() is None  # bob's waits: same phone
    Campaign.objects.filter(pk=a.pk).update(status="completed")
    assert runner.claim_next().pk == b.pk


# ---------- stopping ----------

def test_sharer_stops_sharing(alice, bob, shared):
    s = Share.objects.get(account=shared["account"])
    assert signed_in(alice).delete(f"/api/sharing/shares/{s.id}/").status_code == 204
    assert signed_in(bob).get("/api/accounts/").json()["results"] == []


def test_stopped_share_is_not_used_by_a_queued_campaign(provider, bob, shared):
    camp = Campaign.objects.create(owner=bob, message="hi", status="running", delay_min_seconds=0, delay_max_seconds=0, batch_size=0)
    camp.sender_accounts.add(shared["account"])
    c = Contact.objects.create(owner=bob, phone="8801711111111")
    CampaignTarget.objects.create(campaign=camp, contact=c, recipient_jid="8801711111111@s.whatsapp.net", account_label="")
    Share.objects.filter(account=shared["account"]).delete()
    runner.run_campaign(camp.pk)
    t = camp.targets.get()
    assert t.status == "failed" and "no longer shared" in t.error and provider.sent == []


def test_receiver_removes_a_share(bob, shared):
    s = Share.objects.get(template=shared["template"])
    assert signed_in(bob).delete(f"/api/sharing/shares/{s.id}/").status_code == 204
    assert signed_in(bob).get("/api/templates/").json() == []


def test_others_cannot_remove_a_share(shared):
    carol = User.objects.create_user("carol", password=PW)
    s = Share.objects.first()
    assert signed_in(carol).delete(f"/api/sharing/shares/{s.id}/").status_code == 404
