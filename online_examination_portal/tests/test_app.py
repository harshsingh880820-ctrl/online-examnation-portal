import os
import tempfile
import unittest
import app as portal


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = portal.DB_PATH
        portal.DB_PATH = os.path.join(self.tmp.name, "test.db")
        portal.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        portal.init_db()
        self.client = portal.app.test_client()

    def tearDown(self):
        portal.DB_PATH = self.old_db
        self.tmp.cleanup()

    def login(self, email, password):
        return self.client.post("/login", data={"email": email, "password": password}, follow_redirects=True)

    def test_home_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_student_login(self):
        response = self.login("student@example.com", "Student@123")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student dashboard", response.data)

    def test_staff_can_create_exam(self):
        self.login("teacher@example.com", "Teacher@123")
        response = self.client.post("/exams/new", data={
            "title": "Test Exam", "description": "Test", "duration_minutes": "5"
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Test Exam", response.data)

    def test_student_cannot_access_admin_users(self):
        self.login("student@example.com", "Student@123")
        response = self.client.get("/admin/users")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
