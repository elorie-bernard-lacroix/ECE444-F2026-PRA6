import os
import pytest
from pathlib import Path
import json

from flask import session

BASE_DIR = Path(__file__).resolve().parent.parent
TEST_DB = BASE_DIR / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

from project.app import app, db, login_required
from project.models import Post


def login(client, username, password):
    """Login helper function"""
    return client.post(
        "/login",
        data=dict(username=username, password=password),
        follow_redirects=True,
    )


def logout(client):
    """Logout helper function"""
    return client.get("/logout", follow_redirects=True)


def test_index(client):
    response = client.get("/", content_type="html/text")
    assert response.status_code == 200


def test_database(client):
    """initial test. ensure that the database exists"""
    tester = TEST_DB.is_file()
    assert tester


def test_empty_db(client):
    """Ensure database is blank"""
    rv = client.get("/")
    assert b"No entries yet. Add some!" in rv.data


def test_search(client):
    """Ensure that search displays matching entries."""
    db.session.add(Post("Searchable title", "Searchable text"))
    db.session.commit()

    response = client.get("/search/?query=Searchable")

    assert response.status_code == 200
    assert b"Searchable" in response.data


def test_search_only_text(client):
    """Ensure that search displays matching entries when searching only by text."""
    db.session.add(Post("Another title", "Searchable text"))
    db.session.commit()

    response = client.get("/search/?query=Searchable")

    assert response.status_code == 200
    assert b"Another title" in response.data


def test_search_multiple_results(client):
    """Ensure that search displays multiple matching entries."""
    db.session.add(Post("Searchable title 1", "Searchable text 1"))
    db.session.add(Post("Searchable title 2", "Searchable text 2"))
    db.session.add(Post("Non-searchable title", "Non-searchable text"))
    db.session.commit()

    response = client.get("/search/?query=Searchable")

    assert response.status_code == 200
    assert b"Searchable title 1" in response.data
    assert b"Searchable title 2" in response.data


def test_login_required(client):
    """Ensure protected functions require an authenticated session."""
    called = False

    @login_required
    def protected_view():
        nonlocal called
        called = True
        return "success"

    with app.test_request_context("/protected"):
        response, status_code = protected_view()

    assert status_code == 401
    assert response.get_json() == {
        "status": 0,
        "message": "Please log in.",
    }
    assert called is False

    with app.test_request_context("/protected"):
        session["logged_in"] = True
        response = protected_view()

    assert response == "success"
    assert called is True


def test_login_logout(client):
    """Test login and logout using helper functions"""
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"])
    assert b"You were logged in" in rv.data
    rv = logout(client)
    assert b"You were logged out" in rv.data
    rv = login(client, app.config["USERNAME"] + "x", app.config["PASSWORD"])
    assert b"Invalid username" in rv.data
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"] + "x")
    assert b"Invalid password" in rv.data


def test_messages(client):
    """Ensure that user can post messages"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.post(
        "/add",
        data=dict(title="<Hello>", text="<strong>HTML</strong> allowed here"),
        follow_redirects=True,
    )
    assert b"No entries here so far" not in rv.data
    assert b"&lt;Hello&gt;" in rv.data
    assert b"<strong>HTML</strong> allowed here" in rv.data


def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 0
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 1


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    with app.app_context():
        db.create_all()  # setup
        yield app.test_client()  # tests run here
        db.drop_all()  # teardown
