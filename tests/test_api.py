"""Integration tests for the River Trail REST API"""

VALID_CONTACT = {
    "name": "Alex Nguyen",
    "email": "alex@example.com",
    "phone": "0412 345 678",
    "subject": "trail",
    "message": "Which trail suits beginners in autumn?",
}

VALID_MEMBER = {
    "email": "sam@example.com",
    "password": "password123",
    "first_name": "Sam",
    "surname": "Tran",
    "mobile": "0412345678",
    "dob": "2000-01-01",
    "address": "1 River Rd",
    "city": "Melbourne",
    "state": "VIC",
    "postcode": "3000",
    "trail_types": ["river", "forest"],
    "difficulty": "Moderate",
    "newsletter": True,
}

REVIEW = {"trail_name": "Yarra Loop", "reviewer": "Sam", "rating": 4, "comment": "Lovely walk"}


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"# TYPE" in r.data


def test_homepage_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.mimetype == "text/html"


def test_create_contact(client):
    r = client.post("/api/contacts", json=VALID_CONTACT)
    assert r.status_code == 201
    assert isinstance(r.get_json()["id"], int)


def test_contact_phone_spaces_removed(client):
    client.post("/api/contacts", json=VALID_CONTACT)
    stored = client.get("/api/contacts").get_json()["data"][0]
    assert stored["phone"] == "0412345678"


def test_contact_rejects_bad_input(client):
    bad = {"name": "", "email": "not-an-email", "phone": "12", "message": "short"}
    r = client.post("/api/contacts", json=bad)
    assert r.status_code == 422
    assert len(r.get_json()["errors"]) == 4


def test_contact_script_tags_escaped(client):
    payload = dict(VALID_CONTACT, message="<script>alert(1)</script> hello there")
    client.post("/api/contacts", json=payload)
    stored = client.get("/api/contacts").get_json()["data"][0]["message"]
    assert "<script>" not in stored


def test_contact_search_and_paging(client):
    for i in range(6):
        client.post("/api/contacts", json=dict(VALID_CONTACT, name=f"Person {i}"))
    body = client.get("/api/contacts", query_string={"limit": 5}).get_json()
    assert body["meta"]["total"] == 6
    assert body["meta"]["pages"] == 2
    assert len(body["data"]) == 5
    found = client.get("/api/contacts", query_string={"search": "Person 3"}).get_json()
    assert found["meta"]["total"] == 1


def test_update_contact_status(client):
    cid = client.post("/api/contacts", json=VALID_CONTACT).get_json()["id"]
    assert client.patch(f"/api/contacts/{cid}/status", json={"status": "resolved"}).status_code == 200
    assert client.patch(f"/api/contacts/{cid}/status", json={"status": "done"}).status_code == 400
    assert client.patch("/api/contacts/9999/status", json={"status": "read"}).status_code == 404


def test_delete_contact(client):
    cid = client.post("/api/contacts", json=VALID_CONTACT).get_json()["id"]
    assert client.delete(f"/api/contacts/{cid}").status_code == 200
    assert client.delete(f"/api/contacts/{cid}").status_code == 404


def test_member_signup_and_count(client):
    r = client.post("/api/members", json=VALID_MEMBER)
    assert r.status_code == 201
    assert client.get("/api/members/count").get_json()["count"] == 1


def test_duplicate_member_email_rejected(client):
    client.post("/api/members", json=VALID_MEMBER)
    r = client.post("/api/members", json=VALID_MEMBER)
    assert r.status_code == 409


def test_member_validation(client):
    bad = dict(VALID_MEMBER, password="short", mobile="123", postcode="30000")
    r = client.post("/api/members", json=bad)
    assert r.status_code == 422
    assert len(r.get_json()["errors"]) == 3


def test_review_average(client):
    client.post("/api/reviews", json=REVIEW)
    client.post("/api/reviews", json=dict(REVIEW, rating=5))
    body = client.get("/api/reviews", query_string={"trail": "Yarra Loop"}).get_json()
    assert body["meta"]["total"] == 2
    assert body["avg"] == 4.5


def test_review_rating_out_of_range(client):
    assert client.post("/api/reviews", json=dict(REVIEW, rating=6)).status_code == 422


def test_review_rating_not_a_number(client):
    assert client.post("/api/reviews", json=dict(REVIEW, rating="abc")).status_code == 422


def test_delete_review(client):
    rid = client.post("/api/reviews", json=REVIEW).get_json()["id"]
    assert client.delete(f"/api/reviews/{rid}").status_code == 200
    assert client.delete(f"/api/reviews/{rid}").status_code == 404


# ── Security fixes ──

def test_non_json_write_rejected(client):
    r = client.post("/api/contacts", data="name=x&email=a@b.com", content_type="text/plain")
    assert r.status_code == 415


def test_no_cors_header_sent(client):
    r = client.get("/api/reviews", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in r.headers


def test_email_regex_accepts_subdomains(client):
    payload = dict(VALID_CONTACT, email="alex@mail.example.com.au")
    assert client.post("/api/contacts", json=payload).status_code == 201


def test_email_regex_rejects_missing_domain_part(client):
    payload = dict(VALID_CONTACT, email="alex@example")
    assert client.post("/api/contacts", json=payload).status_code == 422


# ── Query filters after removing dynamic SQL ──

def test_contact_subject_filter(client):
    client.post("/api/contacts", json=VALID_CONTACT)
    client.post("/api/contacts", json=dict(VALID_CONTACT, subject="gear"))
    body = client.get("/api/contacts", query_string={"subject": "gear"}).get_json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["subject"] == "gear"


def test_reviews_without_trail_returns_all(client):
    client.post("/api/reviews", json=REVIEW)
    client.post("/api/reviews", json=dict(REVIEW, trail_name="Dandenong Ridge"))
    body = client.get("/api/reviews").get_json()
    assert body["meta"]["total"] == 2
