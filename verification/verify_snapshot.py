import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))
from app import BundledResults, SNAPSHOT_FILE, create_app


def verify():
    snapshot = BundledResults(SNAPSHOT_FILE)
    assert set(snapshot.recommendation_rows) == {str(user_id) for user_id in range(1, 6041)}
    for user_id, rows in snapshot.recommendation_rows.items():
        assert [row["recommendation_rank"] for row in rows] == list(range(1, 11))
        assert all(row["user_id"] == int(user_id) for row in rows)

    with patch("app.WebHDFS", side_effect=AssertionError("Snapshot tried to connect to HDFS")), \
         patch("app.socket.create_connection", side_effect=AssertionError("Snapshot tried to connect to Kafka")):
        app = create_app({"WEBHDFS": None, "DATA_MODE": None})
        app.testing = True
        client = app.test_client()
        assert b'data-mode="snapshot"' in client.get("/").data

        def get(path):
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
            return response.get_json()

        assert get("/api/overview") == {"rating_count": 1000209, "movie_count": 3883, "user_count": 6040}
        assert sum(count for _, count in get("/api/offline/trend")["daily"]) == 1000209
        assert len(get("/api/offline/hourly")["hourly"]) == 24
        assert len(get("/api/offline/movie-scores")["movies"]) == 2514
        assert len(get("/api/movie/ranking")["movies"]) == 20
        for user_id in (1, 2, 6040):
            result = get(f"/api/recommendations?user_id={user_id}")
            assert result["recommendations"] == snapshot.recommendations(user_id)
        assert client.get("/api/recommendations?user_id=abc").status_code == 400
        assert client.get("/api/recommendations?user_id=6041").status_code == 404
        realtime = get("/api/realtime")
        assert realtime["snapshot_source"] == "bundled" and realtime["kafka_reachable"] is None
        assert len(realtime["windows"]) == 30
        assert len(get("/api/alerts")["alerts"]) == 5

    print("Offline snapshot verified: eight APIs, 6,040 users and 60,400 saved recommendations.")


if __name__ == "__main__":
    verify()
