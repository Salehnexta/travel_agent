import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    """Health endpoint should return healthy status."""
    rv = client.get('/health')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'status' in data and data['status'] == 'healthy'


def test_chat_and_session_flow(client):
    """Full chat flow: chat, follow-up chat, and reset session."""
    # Initial chat
    rv1 = client.post('/api/chat', json={'message': 'Hello travel agent'})
    assert rv1.status_code == 200
    data1 = rv1.get_json()
    assert 'response' in data1 and 'session_id' in data1
    session_id = data1['session_id']

    # Follow-up chat with same session
    rv2 = client.post('/api/chat', json={'message': 'Find flights from DMM to BKK tomorrow'})
    assert rv2.status_code == 200
    data2 = rv2.get_json()
    assert data2.get('session_id') == session_id
    assert 'response' in data2

    # Reset session
    rv3 = client.post('/api/reset')
    assert rv3.status_code == 200
    data3 = rv3.get_json()
    # The reset endpoint returns 'new_session_id'
    assert 'new_session_id' in data3
    assert data3.get('new_session_id') != session_id
